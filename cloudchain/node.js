const crypto = require('crypto');
const EventEmitter = require('events');

class CloudChainRPC extends EventEmitter {
  constructor(options = {}) {
    super();
    this.port = options.port || 8545;
    this.host = options.host || 'localhost';
    this.chainId = options.chainId || 1;
    this.networkId = options.networkId || 1;
    this.isMining = options.isMining || false;
    this.isArchive = options.isArchive || false;
    this.peers = new Map();
    this.transactionPool = [];
    this.blockchain = null;
    this.pendingCallbacks = new Map();
    this.mempool = new Map();
    this.filters = new Map();
    this.filterIdCounter = 0;
    this.masterAddress = options.masterAddress || null;
    this.masterFee = 0.0005;
  }

  setBlockchain(blockchain) {
    this.blockchain = blockchain;
  }

  async handleRequest(method, params) {
    const handlers = {
      'eth_chainId': () => '0x' + this.chainId.toString(16),
      'eth_networkId': () => this.networkId,
      'eth_blockNumber': () => this.blockchain ? '0x' + this.blockchain.getLatestBlockNumber().toString(16) : '0x0',
      'eth_getBalance': (p) => this.blockchain ? '0x' + (this.blockchain.getBalance(p[0]) || 0n).toString(16) : '0x0',
      'eth_getCode': (p) => this.blockchain ? this.blockchain.getCode(p[0]) : '0x',
      'eth_getBlockByNumber': (p) => this.blockchain ? this.blockchain.getBlockByNumber(parseInt(p[0], 16)) : null,
      'eth_getBlockByHash': (p) => this.blockchain ? this.blockchain.getBlockByHash(p[0]) : null,
      'eth_getTransactionByHash': (p) => this.blockchain ? this.blockchain.getTransaction(p[0]) : null,
      'eth_getTransactionReceipt': (p) => this.blockchain ? this.blockchain.getReceipt(p[0]) : null,
      'eth_sendRawTransaction': (p) => this.sendRawTransaction(p[0]),
      'eth_call': (p) => this.ethCall(p[0], p[1]),
      'eth_estimateGas': (p) => this.estimateGas(p[0]),
      'eth_gasPrice': () => '0x' + (this.getGasPrice() || 1000000000n).toString(16),
      'eth_maxPriorityFeePerGas': () => '0x' + (500000000n).toString(16),
      'eth_newBlockFilter': () => this.newBlockFilter(),
      'eth_newPendingTransactionFilter': () => this.newPendingTransactionFilter(),
      'eth_newFilter': (p) => this.newFilter(p[0]),
      'eth_uninstallFilter': (p) => this.uninstallFilter(p[0]),
      'eth_getFilterChanges': (p) => this.getFilterChanges(p[0]),
      'eth_getFilterLogs': (p) => this.getFilterLogs(p[0]),
      'eth_getLogs': (p) => this.getLogs(p[0]),
      'net_version': () => this.networkId.toString(),
      'net_peerCount': () => '0x' + this.peers.size.toString(16),
      'net_listening': () => this.isListening(),
      'web3_clientVersion': () => 'CloudChain/1.0.0',
      'web3_sha3': (p) => '0x' + crypto.createHash('sha3-256').update(p[0].startsWith('0x') ? Buffer.from(p[0].slice(2), 'hex') : Buffer.from(p[0])).digest('hex'),
      'cloudchain_masterFee': () => this.masterFee,
      'cloudchain_setMaster': (p) => this.setMasterAddress(p[0]),
      'cloudchain_getMaster': () => this.masterAddress,
      'cloudchain_isMaster': (p) => this.isMasterNode(p[0]),
      'cloudchain_forkInfo': () => this.getForkInfo()
    };

    if (handlers[method]) {
      try {
        return await handlers[method](params || []);
      } catch (error) {
        return { error: error.message };
      }
    }

    return { error: `Method ${method} not found` };
  }

  async sendRawTransaction(signedTx) {
    try {
      const tx = this.decodeTransaction(signedTx);
      
      const validation = this.validateTransaction(tx);
      if (!validation.valid) {
        throw new Error(validation.error);
      }

      const processedTx = await this.processTransaction(tx);
      this.emit('transaction:new', processedTx);
      
      return processedTx.hash;
    } catch (error) {
      throw new Error(`Transaction failed: ${error.message}`);
    }
  }

  decodeTransaction(signedTx) {
    const txData = signedTx.startsWith('0x') ? signedTx.slice(2) : signedTx;
    const buffer = Buffer.from(txData, 'hex');
    
    return {
      nonce: parseInt(buffer.slice(0, 4).toString('hex'), 16),
      gasPrice: BigInt('0x' + buffer.slice(4, 12).toString('hex')),
      gasLimit: BigInt('0x' + buffer.slice(12, 20).toString('hex')),
      to: '0x' + buffer.slice(20, 40).toString('hex'),
      value: BigInt('0x' + buffer.slice(40, 72).toString('hex')),
      data: '0x' + buffer.slice(72, 136).toString('hex'),
      v: parseInt(buffer.slice(136, 140).toString('hex'), 16),
      r: buffer.slice(140, 172).toString('hex'),
      s: buffer.slice(172, 204).toString('hex'),
      hash: '0x' + crypto.createHash('sha3-256').update(buffer).digest('hex')
    };
  }

  validateTransaction(tx) {
    if (!tx.to && !tx.data) {
      return { valid: false, error: 'Transaction must have a recipient or data' };
    }
    if (tx.gasLimit < 21000n) {
      return { valid: false, error: 'Gas limit too low' };
    }
    if (tx.value < 0n) {
      return { valid: false, error: 'Negative value not allowed' };
    }
    return { valid: true };
  }

  async processTransaction(tx) {
    const txFee = tx.gasLimit * tx.gasPrice;
    const masterFee = txFee * BigInt(Math.floor(this.masterFee * 10000)) / 10000n;
    
    const processedTx = {
      ...tx,
      blockNumber: null,
      blockHash: null,
      transactionIndex: null,
      status: 'pending',
      masterFee: masterFee.toString(),
      masterAddress: this.masterAddress,
      timestamp: Date.now()
    };

    this.mempool.set(tx.hash, processedTx);
    this.emit('mempool:add', processedTx);

    if (this.blockchain) {
      try {
        const result = await this.blockchain.executeTransaction(processedTx);
        processedTx.status = result.success ? 'success' : 'reverted';
        processedTx.blockNumber = this.blockchain.getLatestBlockNumber();
        processedTx.blockHash = this.blockchain.getLatestBlockHash();
        processedTx.returnValue = result.returnValue;
        
        if (this.masterAddress && masterFee > 0n) {
          this.blockchain.transferFee(this.masterAddress, masterFee);
        }
      } catch (error) {
        processedTx.status = 'reverted';
        processedTx.error = error.message;
      }
    }

    return processedTx;
  }

  ethCall(tx, blockNumber = 'latest') {
    if (!this.blockchain) {
      throw new Error('No blockchain connected');
    }
    return this.blockchain.simulateCall(tx, blockNumber);
  }

  estimateGas(tx) {
    const baseGas = 21000n;
    const dataGas = tx.data ? BigInt(tx.data.length / 2) * 68n : 0n;
    return '0x' + (baseGas + dataGas + 10000n).toString(16);
  }

  getGasPrice() {
    const pendingCount = this.mempool.size;
    const basePrice = 1000000000n;
    return basePrice + BigInt(pendingCount * 10000000);
  }

  newBlockFilter() {
    const filterId = '0x' + (++this.filterIdCounter).toString(16);
    this.filters.set(filterId, {
      type: 'blocks',
      latestBlock: this.blockchain?.getLatestBlockNumber() || 0,
      changes: []
    });
    return filterId;
  }

  newPendingTransactionFilter() {
    const filterId = '0x' + (++this.filterIdCounter).toString(16);
    this.filters.set(filterId, {
      type: 'pendingTransactions',
      hashes: []
    });
    return filterId;
  }

  newFilter(filterOptions) {
    const filterId = '0x' + (++this.filterIdCounter).toString(16);
    this.filters.set(filterId, {
      type: 'logs',
      options: filterOptions,
      logs: []
    });
    return filterId;
  }

  uninstallFilter(filterId) {
    return this.filters.delete(filterId);
  }

  getFilterChanges(filterId) {
    const filter = this.filters.get(filterId);
    if (!filter) return [];

    if (filter.type === 'blocks') {
      const newBlock = this.blockchain?.getLatestBlockNumber() || 0;
      if (newBlock > filter.latestBlock) {
        const changes = [];
        for (let i = filter.latestBlock + 1; i <= newBlock; i++) {
          changes.push(this.blockchain.getBlockByNumber(i));
        }
        filter.latestBlock = newBlock;
        return changes;
      }
      return [];
    }

    if (filter.type === 'pendingTransactions') {
      const hashes = Array.from(this.mempool.keys());
      const newHashes = hashes.filter(h => !filter.hashes.includes(h));
      filter.hashes = filter.hashes.concat(newHashes);
      return newHashes;
    }

    return [];
  }

  getFilterLogs(filterId) {
    const filter = this.filters.get(filterId);
    if (!filter || filter.type !== 'logs') return [];
    return this.blockchain?.getLogs(filter.options) || [];
  }

  getLogs(filterOptions) {
    return this.blockchain?.getLogs(filterOptions) || [];
  }

  addPeer(peerInfo) {
    this.peers.set(peerInfo.id, {
      ...peerInfo,
      connected: true,
      added: Date.now()
    });
    this.emit('peer:added', peerInfo);
  }

  removePeer(peerId) {
    this.peers.delete(peerId);
    this.emit('peer:removed', peerId);
  }

  isListening() {
    return this.peers.size > 0;
  }

  setMasterAddress(address) {
    this.masterAddress = address;
    return true;
  }

  isMasterNode(address) {
    return address?.toLowerCase() === this.masterAddress?.toLowerCase();
  }

  getForkInfo() {
    return {
      isFork: this.blockchain?.isFork || false,
      masterAddress: this.masterAddress,
      masterFee: this.masterFee,
      chainId: this.chainId,
      networkId: this.networkId,
      connectedToMaster: this.blockchain?.connectedToMaster || false
    };
  }

  async startServer() {
    const http = require('http');
    
    const server = http.createServer(async (req, res) => {
      if (req.method === 'POST' && req.url === '/') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
          try {
            const { jsonrpc, method, params, id } = JSON.parse(body);
            const result = await this.handleRequest(method, params);
            
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
              jsonrpc: '2.0',
              id,
              result
            }));
          } catch (error) {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
              jsonrpc: '2.0',
              id: 1,
              error: { code: -32601, message: error.message }
            }));
          }
        });
      } else {
        res.writeHead(404);
        res.end();
      }
    });

    return new Promise((resolve) => {
      server.listen(this.port, this.host, () => {
        console.log(`CloudChain RPC listening on ${this.host}:${this.port}`);
        resolve(server);
      });
    });
  }
}

module.exports = CloudChainRPC;