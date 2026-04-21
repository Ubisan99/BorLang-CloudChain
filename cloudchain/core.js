const crypto = require('crypto');
const EventEmitter = require('events');

class CloudChainBlock {
  constructor(blockData = {}) {
    this.number = blockData.number || 0;
    this.hash = blockData.hash || null;
    this.parentHash = blockData.parentHash || '0x' + '0'.repeat(64);
    this.timestamp = blockData.timestamp || Date.now();
    this.transactions = blockData.transactions || [];
    this.stateRoot = blockData.stateRoot || '0x' + '0'.repeat(64);
    this.receiptsRoot = blockData.receiptsRoot || '0x' + '0'.repeat(64);
    this.miner = blockData.miner || '0x' + '0'.repeat(40);
    this.difficulty = blockData.difficulty || 0;
    this.gasLimit = blockData.gasLimit || 30000000n;
    this.gasUsed = blockData.gasUsed || 0n;
    this.extraData = blockData.extraData || '0x';
    this.nonce = blockData.nonce || '0x' + '0'.repeat(16);
    this.size = blockData.size || 0;
    this.totalDifficulty = blockData.totalDifficulty || 0;
    this.transactionsRoot = blockData.transactionsRoot || '0x' + '0'.repeat(64);
    this.chainId = blockData.chainId || 1;
    this.masterFee = blockData.masterFee || 0n;
    this.masterAddress = blockData.masterAddress || null;
    this.forkedFrom = blockData.forkedFrom || null;
  }

  static calculateHash(block) {
    const data = JSON.stringify({
      number: block.number,
      parentHash: block.parentHash,
      timestamp: block.timestamp,
      transactions: block.transactions.map(t => t.hash || t),
      stateRoot: block.stateRoot,
      receiptsRoot: block.receiptsRoot,
      miner: block.miner,
      extraData: block.extraData,
      chainId: block.chainId
    });
    return '0x' + crypto.createHash('sha3-256').update(data).digest('hex');
  }

  seal() {
    this.hash = CloudChainBlock.calculateHash(this);
    this.size = this.calculateSize();
    return this;
  }

  calculateSize() {
    return JSON.stringify(this).length;
  }

  toJSON() {
    return {
      number: this.number,
      hash: this.hash,
      parentHash: this.parentHash,
      timestamp: this.timestamp,
      transactions: this.transactions,
      stateRoot: this.stateRoot,
      receiptsRoot: this.receiptsRoot,
      miner: this.miner,
      difficulty: this.difficulty,
      gasLimit: this.gasLimit.toString(),
      gasUsed: this.gasUsed.toString(),
      extraData: this.extraData,
      nonce: this.nonce,
      size: this.size,
      totalDifficulty: this.totalDifficulty,
      transactionsRoot: this.transactionsRoot,
      chainId: this.chainId,
      masterFee: this.masterFee.toString(),
      masterAddress: this.masterAddress,
      forkedFrom: this.forkedFrom
    };
  }
}

class CloudChain extends EventEmitter {
  constructor(options = {}) {
    super();
    this.chainId = options.chainId || 1;
    this.networkId = options.networkId || 1;
    this.genesisBlock = options.genesisBlock || null;
    this.blocks = new Map();
    this.state = new Map();
    this.addresses = new Map();
    this.contracts = new Map();
    this.transactionReceipts = new Map();
    this.latestBlockNumber = -1;
    this.latestBlockHash = null;
    this.totalDifficulty = 0n;
    this.isFork = options.isFork || false;
    this.forkedFromChainId = options.forkedFromChainId || null;
    this.masterAddress = options.masterAddress || null;
    this.masterFeePercentage = options.masterFeePercentage || 0.0005;
    this.isPrivate = options.isPrivate || false;
    this.maxPrivateUsers = options.maxPrivateUsers || 20;
    this.privateUsers = new Set();
    this.parentChain = options.parentChain || null;
    this.isConnectedToMaster = false;
    this.forkRegistry = new Map();
    this.slots = new Map();
    this.epochs = new Map();
  }

  async initialize() {
    if (this.genesisBlock) {
      const genesis = new CloudChainBlock({
        ...this.genesisBlock,
        chainId: this.chainId
      });
      genesis.seal();
      this.blocks.set(0, genesis);
      this.latestBlockNumber = 0;
      this.latestBlockHash = genesis.hash;
      this.totalDifficulty = 1n;
      
      if (this.isFork && this.parentChain) {
        await this.syncFromParent();
      }
    }
    this.emit('initialized');
  }

  async syncFromParent() {
    if (!this.parentChain) return;
    
    try {
      const parentLatest = this.parentChain.getLatestBlockNumber();
      let syncedCount = 0;
      
      for (let i = 0; i <= parentLatest; i++) {
        const parentBlock = this.parentChain.getBlockByNumber(i);
        if (parentBlock && !this.blocks.has(i)) {
          const forkedBlock = new CloudChainBlock({
            ...parentBlock,
            number: i,
            forkedFrom: parentBlock.hash
          });
          forkedBlock.seal();
          this.blocks.set(i, forkedBlock);
          syncedCount++;
        }
      }
      
      this.latestBlockNumber = this.blocks.size - 1;
      this.latestBlockHash = this.blocks.get(this.latestBlockNumber)?.hash || null;
      this.isConnectedToMaster = true;
      
      this.emit('sync:completed', { syncedBlocks: syncedCount });
    } catch (error) {
      this.emit('sync:failed', { error: error.message });
    }
  }

  addBlock(transactions = [], miner = '0x' + '0'.repeat(40)) {
    const parentBlock = this.blocks.get(this.latestBlockNumber);
    const parentHash = parentBlock?.hash || '0x' + '0'.repeat(64);
    
    let totalMasterFee = 0n;
    const receipts = [];
    
    for (const tx of transactions) {
      const receipt = this.executeTransactionInternal(tx);
      receipts.push(receipt);
      
      if (this.masterAddress && receipt.status === 'success') {
        const fee = (tx.gasLimit || 21000n) * (tx.gasPrice || 0n);
        const masterFee = fee * BigInt(Math.floor(this.masterFeePercentage * 100000)) / 100000n;
        totalMasterFee += masterFee;
      }
    }

    const receiptsRoot = '0x' + crypto.createHash('sha3-256')
      .update(JSON.stringify(receipts)).digest('hex');

    const block = new CloudChainBlock({
      number: this.latestBlockNumber + 1,
      parentHash: parentHash,
      timestamp: Date.now(),
      transactions: transactions,
      stateRoot: this.stateRoot(),
      receiptsRoot: receiptsRoot,
      miner: miner,
      gasLimit: 30000000n,
      gasUsed: receipts.reduce((sum, r) => sum + (r.gasUsed || 0n), 0n),
      chainId: this.chainId,
      masterFee: totalMasterFee,
      masterAddress: this.masterAddress,
      forkedFrom: this.isFork ? parentHash : null
    });

    block.seal();
    this.blocks.set(block.number, block);
    this.latestBlockNumber = block.number;
    this.latestBlockHash = block.hash;
    this.totalDifficulty += 1n;

    for (const receipt of receipts) {
      this.transactionReceipts.set(receipt.transactionHash, receipt);
    }

    this.emit('block:added', block);
    return block;
  }

  executeTransactionInternal(tx) {
    const startGas = tx.gasLimit || 21000n;
    const gasPrice = tx.gasPrice || 0n;
    const gasUsed = startGas;
    const receipt = {
      transactionHash: tx.hash || '0x' + crypto.randomBytes(32).toString('hex'),
      blockNumber: this.latestBlockNumber,
      blockHash: this.latestBlockHash,
      from: tx.from,
      to: tx.to,
      gasUsed: gasUsed.toString(),
      status: 'success',
      logs: [],
      returnValue: '0x'
    };

    try {
      const senderBalance = this.state.get(`balance:${tx.from}`) || 0n;
      const totalCost = tx.value + (gasUsed * gasPrice);
      
      if (senderBalance < totalCost) {
        throw new Error('Insufficient balance');
      }

      this.state.set(`balance:${tx.from}`, senderBalance - totalCost);

      if (tx.to) {
        const receiverBalance = this.state.get(`balance:${tx.to}`) || 0n;
        this.state.set(`balance:${tx.to}`, receiverBalance + tx.value);
      }

      if (tx.data && tx.data !== '0x' && this.contracts.has(tx.to)) {
        const contract = this.contracts.get(tx.to);
        receipt.returnValue = contract.execute(tx.data) || '0x';
      }

      receipt.status = 'success';
    } catch (error) {
      receipt.status = 'reverted';
      receipt.error = error.message;
    }

    return receipt;
  }

  executeTransaction(tx) {
    const receipt = this.executeTransactionInternal(tx);
    this.transactionReceipts.set(receipt.transactionHash, receipt);
    this.emit('transaction:executed', { tx, receipt });
    return receipt;
  }

  stateRoot() {
    return '0x' + crypto.createHash('sha3-256')
      .update(JSON.stringify(Array.from(this.state.entries()))).digest('hex');
  }

  getBalance(address) {
    return this.state.get(`balance:${address}`) || 0n;
  }

  setBalance(address, balance) {
    this.state.set(`balance:${address}`, balance);
  }

  transfer(from, to, amount) {
    const fromBalance = this.getBalance(from);
    if (fromBalance < amount) {
      throw new Error('Insufficient balance');
    }
    this.setBalance(from, fromBalance - amount);
    this.setBalance(to, this.getBalance(to) + amount);
  }

  transferFee(to, amount) {
    if (this.masterAddress) {
      this.setBalance(to, this.getBalance(to) + amount);
    }
  }

  deployContract(address, code, state = {}) {
    this.contracts.set(address, {
      code: code,
      state: state,
      execute: (data) => {
        return '0x' + crypto.createHash('sha3-256').update(data).digest('hex').slice(0, 8);
      }
    });
    this.state.set(`code:${address}`, code);
  }

  getCode(address) {
    return this.state.get(`code:${address}`) || '0x';
  }

  getBlockByNumber(number) {
    return this.blocks.get(number)?.toJSON() || null;
  }

  getBlockByHash(hash) {
    for (const [_, block] of this.blocks) {
      if (block.hash === hash) return block.toJSON();
    }
    return null;
  }

  getTransaction(hash) {
    for (const [_, block] of this.blocks) {
      const tx = block.transactions.find(t => t.hash === hash);
      if (tx) return tx;
    }
    return null;
  }

  getReceipt(hash) {
    return this.transactionReceipts.get(hash) || null;
  }

  getLatestBlockNumber() {
    return this.latestBlockNumber;
  }

  getLatestBlockHash() {
    return this.latestBlockHash;
  }

  simulateCall(tx, blockNumber = 'latest') {
    const snapshotId = this.stateSnapshot();
    
    try {
      const result = this.executeTransactionInternal(tx);
      this.restoreSnapshot(snapshotId);
      return result.returnValue || '0x';
    } catch (error) {
      this.restoreSnapshot(snapshotId);
      throw error;
    }
  }

  stateSnapshot() {
    return new Map(this.state);
  }

  restoreSnapshot(snapshot) {
    this.state = new Map(snapshot);
  }

  getLogs(filterOptions) {
    const logs = [];
    for (const receipt of this.transactionReceipts.values()) {
      if (receipt.logs && receipt.logs.length > 0) {
        logs.push(...receipt.logs);
      }
    }
    return logs;
  }

  registerFork(forkInfo) {
    this.forkRegistry.set(forkInfo.chainId, {
      ...forkInfo,
      registeredAt: Date.now()
    });
  }

  verifyForkConnection(forkChainId) {
    const forkInfo = this.forkRegistry.get(forkChainId);
    if (!forkInfo) {
      return { valid: false, reason: 'Fork not registered' };
    }
    
    if (forkInfo.masterAddress !== this.masterAddress) {
      return { valid: false, reason: 'Master address mismatch' };
    }
    
    return { valid: true, forkInfo };
  }

  addPrivateUser(userAddress) {
    if (!this.isPrivate) {
      throw new Error('This is not a private chain');
    }
    if (this.privateUsers.size >= this.maxPrivateUsers) {
      throw new Error(`Maximum private users (${this.maxPrivateUsers}) reached`);
    }
    this.privateUsers.add(userAddress);
    return this.privateUsers.size;
  }

  removePrivateUser(userAddress) {
    return this.privateUsers.delete(userAddress);
  }

  isPrivateUser(userAddress) {
    return this.isPrivate ? this.privateUsers.has(userAddress) : true;
  }

  getChainInfo() {
    return {
      chainId: this.chainId,
      networkId: this.networkId,
      latestBlock: this.latestBlockNumber,
      latestBlockHash: this.latestBlockHash,
      totalDifficulty: this.totalDifficulty.toString(),
      isFork: this.isFork,
      forkedFrom: this.forkedFromChainId,
      isPrivate: this.isPrivate,
      privateUsersCount: this.privateUsers.size,
      maxPrivateUsers: this.maxPrivateUsers,
      masterAddress: this.masterAddress,
      masterFeePercentage: this.masterFeePercentage,
      isConnectedToMaster: this.isConnectedToMaster,
      forks: Array.from(this.forkRegistry.keys())
    };
  }
}

module.exports = CloudChain;
module.exports.CloudChainBlock = CloudChainBlock;