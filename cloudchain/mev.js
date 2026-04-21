const crypto = require('crypto');
const EventEmitter = require('events');

class CloudChainSecurity extends EventEmitter {
  constructor(options = {}) {
    super();
    this.blockWindow = options.blockWindow || 12;
    this.frontRunningProtection = options.frontRunningProtection !== false;
    this.sandwichProtection = options.sandwichProtection !== false;
    this.sniperProtection = options.sniperProtection !== false;
    this.fraudDetection = options.fraudDetection !== false;
    this.maxGasPriceMultiplier = options.maxGasPriceMultiplier || 5;
    this.suspiciousPatterns = new Map();
    this.blockedAddresses = new Set();
    this.verifiedFlashBots = new Set();
    this.transactionWhitelist = new Set();
    this.fraudScore = new Map();
    this.maxFraudScore = 100;
  }

  analyzeTransaction(tx, mempool) {
    const analysis = {
      txHash: tx.hash,
      isSuspicious: false,
      riskLevel: 'none',
      issues: [],
      recommendations: [],
      frontRunRisk: 0,
      sandwichRisk: 0,
      sniperRisk: 0,
      fraudScore: 0
    };

    if (this.frontRunningProtection) {
      const frontRunAnalysis = this.detectFrontRunning(tx, mempool);
      analysis.frontRunRisk = frontRunAnalysis.risk;
      if (frontRunAnalysis.risk > 50) {
        analysis.isSuspicious = true;
        analysis.issues.push('High front-running risk detected');
        analysis.riskLevel = 'high';
      }
    }

    if (this.sandwichProtection) {
      const sandwichAnalysis = this.detectSandwich(tx, mempool);
      analysis.sandwichRisk = sandwichAnalysis.risk;
      if (sandwichAnalysis.risk > 50) {
        analysis.isSuspicious = true;
        analysis.issues.push('Potential sandwich attack detected');
        analysis.riskLevel = 'high';
      }
    }

    if (this.sniperProtection) {
      const sniperAnalysis = this.detectSniping(tx, mempool);
      analysis.sniperRisk = sniperAnalysis.risk;
      if (sniperAnalysis.risk > 70) {
        analysis.isSuspicious = true;
        analysis.issues.push('MEV sniper detected');
        analysis.riskLevel = 'critical';
      }
    }

    if (this.fraudDetection) {
      const fraudAnalysis = this.detectFraud(tx);
      analysis.fraudScore = fraudAnalysis.score;
      if (fraudAnalysis.isFraudulent) {
        analysis.isSuspicious = true;
        analysis.issues.push(...fraudAnalysis.issues);
        if (analysis.riskLevel !== 'critical') {
          analysis.riskLevel = fraudAnalysis.level;
        }
      }
    }

    if (tx.gasPrice) {
      const gasAnalysis = this.analyzeGasPrice(tx);
      if (gasAnalysis.isExcessive) {
        analysis.issues.push(gasAnalysis.message);
        analysis.fraudScore += gasAnalysis.score;
        if (!analysis.isSuspicious) {
          analysis.isSuspicious = true;
        }
      }
    }

    if (analysis.fraudScore > 50) {
      analysis.riskLevel = 'high';
    } else if (analysis.fraudScore > 30) {
      analysis.riskLevel = analysis.riskLevel === 'none' ? 'medium' : analysis.riskLevel;
    }

    analysis.recommendations = this.generateRecommendations(analysis);

    this.emit('transaction:analyzed', analysis);
    return analysis;
  }

  detectFrontRunning(tx, mempool) {
    let risk = 0;

    const similarTxs = mempool.filter(mtx => {
      if (mtx.from === tx.from) return false;
      if (mtx.to === tx.to && mtx.data && tx.data) {
        const similarity = this.calculateDataSimilarity(mtx.data, tx.data);
        return similarity > 0.8;
      }
      return false;
    });

    if (similarTxs.length > 3) {
      risk += 30;
    }

    const pendingSameTarget = mempool.filter(mtx => 
      mtx.to === tx.to && 
      mtx.timestamp > tx.timestamp - 5000
    );

    if (pendingSameTarget.length > 0) {
      risk += 20;
    }

    const gasPricePercentile = this.getGasPricePercentile(mempool, tx.gasPrice);
    if (gasPricePercentile > 90) {
      risk += 25;
    }

    return { risk: Math.min(risk, 100), detected: risk > 50 };
  }

  detectSandwich(tx, mempool) {
    let risk = 0;

    const buyOrders = mempool.filter(mtx => {
      if (!mtx.data) return false;
      return mtx.data.startsWith('0x095ea7b3') && mtx.to === tx.to;
    });

    const sellOrders = mempool.filter(mtx => {
      if (!mtx.data) return false;
      return mtx.data.startsWith('0xa0712d68') && mtx.to === tx.to;
    });

    if (buyOrders.length > 0 && sellOrders.length > 0) {
      risk += 50;
    }

    if (tx.value > 0n) {
      const sandwichPotential = mempool.filter(mtx => {
        const timeDiff = Math.abs(mtx.timestamp - tx.timestamp);
        return timeDiff < 1000 && mtx.to === tx.to;
      });

      if (sandwichPotential.length >= 2) {
        risk += 40;
      }
    }

    const totalValue = [...buyOrders, ...sellOrders].reduce((sum, mtx) => sum + mtx.value, 0n);
    if (totalValue > tx.value * 10n) {
      risk += 10;
    }

    return { risk: Math.min(risk, 100), detected: risk > 50 };
  }

  detectSniping(tx, mempool) {
    let risk = 0;

    if (!tx.data || tx.data.length < 10) {
      return { risk: 0, detected: false };
    }

    if (tx.data.startsWith('0x5c60da1b')) {
      risk += 80;
    }

    const newPairs = mempool.filter(mtx => 
      mtx.data && mtx.data.startsWith('0xe8a37d09')
    );

    if (newPairs.length > 0) {
      const token = this.extractTokenFromTx(tx);
      if (token && newPairs.some(np => this.extractTokenFromTx(np) === token)) {
        risk += 70;
      }
    }

    constniper = mempool.filter(mtx => {
      if (mtx.timestamp < tx.timestamp - 300000) return false;
      if (mtx.from === tx.from) return false;
      const gasMultiplier = Number(tx.gasPrice) / Number(mtx.gasPrice || 1n);
      return gasMultiplier > 3;
    });

    if (snipers.length > 5) {
      risk += 30;
    }

    return { risk: Math.min(risk, 100), detected: risk > 70 };
  }

  detectFraud(tx) {
    const issues = [];
    let score = 0;
    let level = 'none';

    const existingReport = this.fraudScore.get(tx.from);
    if (existingReport && existingReport > 50) {
      score += 30;
      issues.push('Sender has fraud history');
    }

    if (this.blockedAddresses.has(tx.from)) {
      score += 50;
      issues.push('Sender is on blocklist');
    }

    if (!tx.signature) {
      score += 10;
      issues.push('Unsigned transaction');
    }

    if (tx.value > 0n && (!tx.to || tx.to === '0x0000000000000000000000000000000000000000')) {
      score += 40;
      issues.push('Invalid recipient for value transfer');
    }

    if (tx.data && tx.data.startsWith('0x') && tx.data !== '0x') {
      const funcSig = tx.data.slice(0, 10);
      const dangerousSigs = [
        '0x3ccfd60b', '0x73204f27', '0x2e1a7d4d', '0x095ea7b3',
        '0xa0712d68', '0x23b872dd', '0xfff6a5db'
      ];
      
      if (dangerousSigs.includes(funcSig)) {
        score += 15;
      }
    }

    if (tx.nonce === 0 && tx.value > 1000000000000000000n) {
      score += 25;
      issues.push('High value from new account (honeypot risk)');
    }

    const contractCreationWithValue = tx.to === null && tx.value > 0n;
    if (contractCreationWithValue) {
      score += 30;
      issues.push('Contract creation with value (potential scam)');
    }

    if (score > 50) {
      level = 'critical';
      this.updateFraudScore(tx.from, 30);
    } else if (score > 30) {
      level = 'high';
      this.updateFraudScore(tx.from, 15);
    } else if (score > 10) {
      level = 'medium';
      this.updateFraudScore(tx.from, 5);
    }

    return {
      score,
      isFraudulent: score > 30,
      issues,
      level
    };
  }

  analyzeGasPrice(tx) {
    const baselineGas = 1000000000n;
    const maxGas = baselineGas * BigInt(this.maxGasPriceMultiplier);
    
    if (tx.gasPrice > maxGas) {
      return {
        isExcessive: true,
        message: `Gas price ${tx.gasPrice} exceeds maximum ${maxGas}`,
        score: Math.min(Number((tx.gasPrice - baselineGas) / 10000000n), 30)
      };
    }

    const multiplier = Number(tx.gasPrice) / Number(baselineGas);
    if (multiplier > 3) {
      return {
        isExcessive: true,
        message: 'Unusually high gas price (potential priority fee abuse)',
        score: Math.min(Math.floor(multiplier * 5), 20)
      };
    }

    return { isExcessive: false };
  }

  calculateDataSimilarity(data1, data2) {
    if (data1 === data2) return 1;
    if (!data1 || !data2) return 0;
    
    const set1 = new Set(data1.match(/.{1,8}/g) || []);
    const set2 = new Set(data2.match(/.{1,8}/g) || []);
    
    const intersection = [...set1].filter(x => set2.has(x));
    const union = new Set([...set1, ...set2]);
    
    return intersection.length / union.size;
  }

  getGasPricePercentile(mempool, gasPrice) {
    if (mempool.length === 0) return 0;
    
    const sorted = [...mempool].sort((a, b) => 
      Number((a.gasPrice || 0n) - (b.gasPrice || 0n))
    );
    
    const index = sorted.findIndex(mtx => (mtx.gasPrice || 0n) >= gasPrice);
    return (index / sorted.length) * 100;
  }

  extractTokenFromTx(tx) {
    if (!tx.data || tx.data.length < 74) return null;
    return '0x' + tx.data.slice(34, 74);
  }

  generateRecommendations(analysis) {
    const recommendations = [];

    if (analysis.frontRunRisk > 30) {
      recommendations.push('Consider using private transactions or Flashbots Protect');
    }

    if (analysis.sandwichRisk > 30) {
      recommendations.push('Use AMM with anti-sandwich protections or limit orders');
    }

    if (analysis.sniperRisk > 50) {
      recommendations.push('Delay large trades or use time-weighted average pricing');
    }

    if (analysis.fraudScore > 20) {
      recommendations.push('Transaction flagged - manual review recommended');
    }

    if (analysis.issues.length > 0) {
      recommendations.push(`Issues detected: ${analysis.issues.join(', ')}`);
    }

    return recommendations;
  }

  updateFraudScore(address, increment) {
    const currentScore = this.fraudScore.get(address) || 0;
    const newScore = Math.min(currentScore + increment, this.maxFraudScore);
    this.fraudScore.set(address, newScore);
    
    if (newScore >= this.maxFraudScore) {
      this.blockAddress(address);
    }
  }

  blockAddress(address) {
    this.blockedAddresses.add(address);
    this.emit('address:blocked', address);
  }

  unblockAddress(address) {
    this.blockedAddresses.delete(address);
    this.emit('address:unblocked', address);
  }

  addToWhitelist(address) {
    this.transactionWhitelist.add(address);
  }

  removeFromWhitelist(address) {
    this.transactionWhitelist.delete(address);
  }

  addVerifiedFlashBot(address) {
    this.verifiedFlashBots.add(address);
  }

  isWhitelisted(address) {
    return this.transactionWhitelist.has(address);
  }

  isVerifiedFlashBot(address) {
    return this.verifiedFlashBots.has(address);
  }

  getBlocklist() {
    return Array.from(this.blockedAddresses);
  }

  getFraudScores() {
    return Array.from(this.fraudScore.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 100);
  }

  clearOldSuspiciousPatterns(maxAge = 3600000) {
    const now = Date.now();
    for (const [key, value] of this.suspiciousPatterns) {
      if (now - value.timestamp > maxAge) {
        this.suspiciousPatterns.delete(key);
      }
    }
  }

  getSecurityReport() {
    return {
      blockedAddresses: this.blockedAddresses.size,
      whitelistedAddresses: this.transactionWhitelist.size,
      verifiedFlashbots: this.verifiedFlashBots.size,
      avgFraudScore: this.getFraudScores().reduce((sum, [_, score]) => sum + score, 0) / Math.max(this.fraudScore.size, 1),
      topRiskAddresses: this.getFraudScores().slice(0, 10)
    };
  }
}

module.exports = CloudChainSecurity;