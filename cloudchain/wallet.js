const crypto = require('crypto');
const { promises: fs } = require('fs');
const path = require('path');

class CloudChainWallet {
  constructor(options = {}) {
    this.key = null;
    this.iv = null;
    this.address = null;
    this.publicKey = null;
    this.seedPhrase = null;
    this.multisig = options.multisig || false;
    this.multisigOwners = options.owners || [];
    this.multisigThreshold = options.threshold || 1;
    this.nonce = 0;
    this.balance = 0n;
    this.transactions = [];
    this.encryptedKey = null;
  }

  static WORDLIST = [
    'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract', 'absurd', 'abuse',
    'access', 'accident', 'account', 'accuse', 'achieve', 'acid', 'acoustic', 'acquire', 'across', 'act',
    'action', 'actor', 'actress', 'actual', 'adapt', 'add', 'addict', 'address', 'adjust', 'admit',
    'adult', 'advance', 'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again', 'age', 'agent',
    'agree', 'ahead', 'aim', 'air', 'airport', 'aisle', 'alarm', 'album', 'alcohol', 'alert'
  ];

  static generateSeedPhrase(words = 24) {
    const entropy = crypto.randomBytes(32);
    const wordlist = CloudChainWallet.WORDLIST;
    const indices = [];
    
    for (let i = 0; i < words; i++) {
      const index = entropy.readUInt16BE((i * 2) % 32) % wordlist.length;
      indices.push(wordlist[index]);
    }
    
    return indices.join(' ');
  }

  static async createFromSeed(seedPhrase, password = null) {
    const wallet = new CloudChainWallet();
    
    const seed = crypto.createHash('sha256').update(seedPhrase).digest();
    wallet.seedPhrase = seedPhrase;
    
    const keyMaterial = password 
      ? crypto.pbkdf2Sync(password, seed, 100000, 32, 'sha512')
      : seed;
    
    wallet.key = crypto.createHash('sha256').update(keyMaterial).digest();
    wallet.iv = crypto.randomBytes(16);
    
    const publicKey = crypto.createPublicKey({
      key: wallet.key,
      type: 'ec',
      namedCurve: 'secp256k1'
    });
    
    wallet.publicKey = publicKey.export({ type: 'spki', format: 'der' });
    wallet.address = '0x' + crypto.createHash('sha3-256').update(wallet.publicKey).digest('hex').slice(0, 40);
    
    if (password) {
      wallet.encryptedKey = wallet.encryptKey(wallet.key, password);
    }
    
    return wallet;
  }

  static async createMultisig(owners, threshold) {
    if (owners.length < 2) {
      throw new Error('Multisig requires at least 2 owners');
    }
    if (threshold > owners.length) {
      throw new Error('Threshold cannot exceed number of owners');
    }
    
    const wallet = new CloudChainWallet({
      multisig: true,
      owners: owners,
      threshold: threshold
    });
    
    const combinedSeed = owners.map(o => o.address).sort().join('+');
    const seed = crypto.createHash('sha256').update(combinedSeed).digest();
    
    wallet.address = '0x' + crypto.createHash('sha3-256').update(seed).digest('hex').slice(0, 40);
    wallet.publicKey = seed.slice(0, 65);
    
    return wallet;
  }

  encryptKey(key, password) {
    const salt = crypto.randomBytes(32);
    const key_ = crypto.pbkdf2Sync(password, salt, 100000, 32, 'sha512');
    const iv = crypto.randomBytes(16);
    
    const cipher = crypto.createCipheriv('aes-256-gcm', key_, iv);
    const encrypted = Buffer.concat([cipher.update(key), cipher.final()]);
    const authTag = cipher.getAuthTag();
    
    return {
      salt: salt.toString('hex'),
      iv: iv.toString('hex'),
      data: encrypted.toString('hex'),
      authTag: authTag.toString('hex')
    };
  }

  decryptKey(encryptedKey, password) {
    const salt = Buffer.from(encryptedKey.salt, 'hex');
    const iv = Buffer.from(encryptedKey.iv, 'hex');
    const key_ = crypto.pbkdf2Sync(password, salt, 100000, 32, 'sha512');
    
    const decipher = crypto.createDecipheriv('aes-256-gcm', key_, iv);
    decipher.setAuthTag(Buffer.from(encryptedKey.authTag, 'hex'));
    
    return Buffer.concat([decipher.update(Buffer.from(encryptedKey.data, 'hex')), decipher.final()]);
  }

  signTransaction(tx, password = null) {
    let signingKey = this.key;
    
    if (this.encryptedKey && password) {
      signingKey = this.decryptKey(this.encryptedKey, password);
    }
    
    if (!signingKey) {
      throw new Error('No signing key available');
    }
    
    const txData = JSON.stringify({
      to: tx.to,
      value: tx.value.toString(),
      data: tx.data || '0x',
      nonce: this.nonce,
      gasPrice: tx.gasPrice || 0,
      gasLimit: tx.gasLimit || 21000
    });
    
    const signature = crypto.createSign('SHA256').update(txData).sign(signingKey);
    this.nonce++;
    
    return {
      ...tx,
      from: this.address,
      nonce: this.nonce - 1,
      signature: signature.toString('hex'),
      hash: crypto.createHash('sha3-256').update(txData + signature).digest('hex')
    };
  }

  signMultisigTransaction(tx, signatures = []) {
    if (!this.multisig) {
      throw new Error('Wallet is not a multisig wallet');
    }
    
    signatures.push({
      signer: this.address,
      signature: this.signTransaction(tx).signature
    });
    
    if (signatures.length >= this.multisigThreshold) {
      return {
        ...tx,
        signatures: signatures,
        executed: true,
        hash: crypto.createHash('sha3-256').update(JSON.stringify(signatures)).digest('hex')
      };
    }
    
    return {
      ...tx,
      signatures: signatures,
      executed: false,
      pendingSignatures: this.multisigThreshold - signatures.length
    };
  }

  async save(walletPath, password = null) {
    const walletData = {
      address: this.address,
      publicKey: this.publicKey.toString('hex'),
      encryptedKey: this.encryptedKey,
      multisig: this.multisig,
      multisigOwners: this.multisigOwners,
      multisigThreshold: this.multisigThreshold,
      nonce: this.nonce,
      balance: this.balance.toString()
    };
    
    await fs.writeFile(
      walletPath,
      JSON.stringify(walletData, null, 2),
      'utf-8'
    );
    
    return walletData;
  }

  static async load(walletPath, password = null) {
    const data = JSON.parse(await fs.readFile(walletPath, 'utf-8'));
    
    const wallet = new CloudChainWallet({
      multisig: data.multisig,
      owners: data.multisigOwners,
      threshold: data.multisigThreshold
    });
    
    wallet.address = data.address;
    wallet.publicKey = Buffer.from(data.publicKey, 'hex');
    wallet.encryptedKey = data.encryptedKey;
    wallet.nonce = data.nonce;
    wallet.balance = BigInt(data.balance);
    
    if (password && data.encryptedKey) {
      wallet.key = wallet.decryptKey(data.encryptedKey, password);
    }
    
    return wallet;
  }

  getAddress() {
    return this.address;
  }

  getPublicKey() {
    return this.publicKey.toString('hex');
  }

  toString() {
    return JSON.stringify({
      address: this.address,
      publicKey: this.getPublicKey(),
      multisig: this.multisig,
      balance: this.balance.toString()
    }, null, 2);
  }
}

module.exports = CloudChainWallet;