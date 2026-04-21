const crypto = require('crypto');
const EventEmitter = require('events');

class BatchTransactionManager extends EventEmitter {
  constructor(options = {}) {
    super();
    this.maxBatchSize = options.maxBatchSize || 100;
    this.maxBatchValue = options.maxBatchValue || BigInt('0x' + 'ffffffffff', 16);
    this.batches = new Map();
    this.pendingTransactions = [];
    this.batchIdCounter = 0;
    this.revertOnFailure = options.revertOnFailure !== false;
    this.atomicMode = options.atomicMode || false;
  }

  createBatch(sender, transactions, options = {}) {
    if (transactions.length > this.maxBatchSize) {
      throw new Error(`Batch size exceeds maximum of ${this.maxBatchSize}`);
    }

    let totalValue = transactions.reduce((sum, tx) => sum + (tx.value || 0n), 0n);
    if (totalValue > this.maxBatchValue) {
      throw new Error(`Total batch value exceeds maximum`);
    }

    const batchId = '0x' + (++this.batchIdCounter).toString(16).padStart(8, '0');
    
    const batch = {
      id: batchId,
      sender: sender,
      transactions: transactions.map((tx, index) => ({
        ...tx,
        batchId: batchId,
        index: index,
        status: 'pending',
        dependencies: tx.dependencies || [],
        revertOnFail: tx.revertOnFail ?? this.revertOnFailure
      })),
      options: {
        atomic: options.atomic ?? this.atomicMode,
        revertOnFailure: options.revertOnFailure ?? this.revertOnFailure,
        gasLimit: options.gasLimit || 0,
        gasPrice: options.gasPrice || 0n
      },
      status: 'pending',
      created: Date.now(),
      executed: null
    };

    this.batches.set(batchId, batch);
    this.emit('batch:created', batch);
    
    return batch;
  }

  addToBatch(batchId, transaction) {
    const batch = this.batches.get(batchId);
    if (!batch) {
      throw new Error('Batch not found');
    }

    if (batch.transactions.length >= this.maxBatchSize) {
      throw new Error('Batch is full');
    }

    const tx = {
      ...transaction,
      batchId: batchId,
      index: batch.transactions.length,
      status: 'pending',
      dependencies: transaction.dependencies || [],
      revertOnFail: transaction.revertOnFail ?? batch.options.revertOnFailure
    };

    batch.transactions.push(tx);
    this.emit('batch:txAdded', { batchId, transaction: tx });

    return tx;
  }

  validateBatchDependencies(batchId) {
    const batch = this.batches.get(batchId);
    if (!batch) return { valid: false, error: 'Batch not found' };

    const executedIndexes = new Set();
    const pending = new Set();
    const hasCircularDependency = (tx, visited = new Set()) => {
      if (visited.has(tx.index)) return true;
      if (pending.has(tx.index)) return true;

      visited.add(tx.index);
      
      for (const depIndex of tx.dependencies) {
        if (depIndex >= batch.transactions.length) {
          throw new Error(`Dependency out of bounds: ${depIndex}`);
        }
        if (depIndex === tx.index) {
          throw new Error(`Self-referential dependency at index ${tx.index}`);
        }
        const depTx = batch.transactions[depIndex];
        if (hasCircularDependency(depTx, new Set(visited))) {
          throw new Error(`Circular dependency detected: ${tx.index} -> ${depIndex}`);
        }
      }
      
      return false;
    };

    for (const tx of batch.transactions) {
      if (tx.dependencies.length > 0) {
        hasCircularDependency(tx);
      }
    }

    return { valid: true };
  }

  async executeBatch(batchId) {
    const batch = this.batches.get(batchId);
    if (!batch) {
      throw new Error('Batch not found');
    }

    const validation = this.validateBatchDependencies(batchId);
    if (!validation.valid) {
      throw new Error(validation.error);
    }

    batch.status = 'executing';
    this.emit('batch:executing', batch);

    const executedResults = [];
    const balanceChanges = new Map();
    const stateSnapshots = [];

    try {
      const results = await Promise.all(
        batch.transactions.map(async (tx, index) => {
          if (tx.dependencies.length > 0) {
            const unmetDeps = tx.dependencies.filter(depIndex => {
              const depResult = executedResults[depIndex];
              return !depResult || depResult.status === 'reverted';
            });
            if (unmetDeps.length > 0) {
              return { status: 'reverted', error: 'Unmet dependencies' };
            }
          }

          try {
            const result = await this.simulateExecute(tx, balanceChanges, batch);
            
            if (result.success) {
              const senderBalance = balanceChanges.get(tx.from) || 0n;
              const newBalance = senderBalance - tx.value - (tx.gasLimit * (tx.gasPrice || 0n));
              
              if (newBalance < 0n) {
                throw new Error('Insufficient balance');
              }
              
              balanceChanges.set(tx.from, newBalance);

              if (tx.to) {
                const receiverBalance = balanceChanges.get(tx.to) || 0n;
                balanceChanges.set(tx.to, receiverBalance + tx.value);
              }
            }

            executedResults[index] = result;
            return result;
          } catch (error) {
            const result = { status: 'reverted', error: error.message };
            executedResults[index] = result;
            
            if (tx.revertOnFail || batch.options.revertOnFailure || batch.options.atomic) {
              throw new Error(`Batch reverted at transaction ${index}: ${error.message}`);
            }
            
            return result;
          }
        })
      );

      batch.status = 'completed';
      batch.executed = Date.now();
      batch.results = executedResults;
      
      this.emit('batch:completed', batch);
      
      return {
        batchId: batch.id,
        status: 'completed',
        results: executedResults
      };

    } catch (error) {
      const revertedBatch = this.revertBatch(batchId, balanceChanges, executedResults);
      
      batch.status = 'reverted';
      batch.reverted = Date.now();
      batch.revertError = error.message;
      
      this.emit('batch:reverted', revertedBatch);
      
      return {
        batchId: batch.id,
        status: 'reverted',
        error: error.message,
        revertedTransactions: revertedBatch.revertedCount
      };
    }
  }

  async simulateExecute(tx, balanceChanges, batch) {
    return {
      success: true,
      status: 'executed',
      gasUsed: tx.gasLimit || 21000n,
      returnValue: '0x'
    };
  }

  revertBatch(batchId, originalBalances, results) {
    const batch = this.batches.get(batchId);
    if (!batch) return null;

    let revertedCount = 0;
    for (let i = results.length - 1; i >= 0; i--) {
      if (results[i]?.status === 'executed') {
        revertedCount++;
      }
    }

    return {
      batchId: batch.id,
      reverted: Date.now(),
      revertedCount: revertedCount,
      originalBalances: Array.from(originalBalances.entries())
    };
  }

  cancelBatch(batchId, sender) {
    const batch = this.batches.get(batchId);
    if (!batch) {
      throw new Error('Batch not found');
    }

    if (batch.sender !== sender) {
      throw new Error('Only batch sender can cancel');
    }

    if (batch.status === 'completed' || batch.status === 'reverted') {
      throw new Error('Batch already executed');
    }

    batch.status = 'cancelled';
    batch.cancelled = Date.now();
    
    this.emit('batch:cancelled', batch);
    
    return batch;
  }

  getBatch(batchId) {
    return this.batches.get(batchId);
  }

  getPendingBatches() {
    return Array.from(this.batches.values()).filter(b => b.status === 'pending');
  }

  getExecutedBatches() {
    return Array.from(this.batches.values()).filter(b => b.status === 'completed' || b.status === 'reverted');
  }

  clearCompleted() {
    let cleared = 0;
    for (const [id, batch] of this.batches) {
      if (batch.status === 'completed' || batch.status === 'reverted' || batch.status === 'cancelled') {
        this.batches.delete(id);
        cleared++;
      }
    }
    return cleared;
  }
}

module.exports = BatchTransactionManager;