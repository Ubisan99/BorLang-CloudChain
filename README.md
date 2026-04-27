# CloudChain

<p align="center">
  <img src="https://img.shields.io/badge/Version-Beta-yellow?style=for-the-badge&logo=blockchain" alt="Version">
  <img src="https://img.shields.io/badge/License-Custom%20Open%20Source-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Status-Testing-orange?style=for-the-badge" alt="Status">
</p>

> ⚠️ **VERSIONE BETA** - Questo progetto è in fase di test. Sono necessari sviluppatori, utenti e nodi per renderlo pienamente operativo.

CloudChain è una piattaforma blockchain Layer 1 con architettura modulare a 4 layer, designed per l'integrazione nativa con intelligenza artificiale, smart contract avanzati e distribuzione legale di file open-source.

## Caratteristiche Principali

### Layer 1 - Consensus (aBFT)
- Protocollo Asynchronous Byzantine Fault Tolerant
- Ispirato da Hedera Hashgraph
- Nessun mining - energia quasi zero
- Finalità asincrona (<5 secondi)

### Layer 2 - AI Compute
- Integrazione nativa Ollama per inferenza AI
- Distribuzione carichi di lavoro AI decentralizzata
- Modelli locali on-chain

### Layer 3 - Smart Contracts
- **Borlang**: Linguaggio proprietario per smart contract
- Primitivi AI nativi
- Distribuzione file legale (anti-pirateria)

### Layer 4 - Orchestration
- Resource allocation intelligente
- Service discovery
- API Gateway

## Wallet AES Customizzato

CloudChain include un sistema wallet avanzato con:

- ✅ Crittografia AES-256-GCM
- ✅ Frasi seed (BIP-39 style)
- ✅ Supporto Multisig opzionale
- ✅ Protezione con password
- ✅ Firme transaction secure

```javascript
const wallet = await CloudChainWallet.createFromSeed(seedPhrase, password);
const signedTx = wallet.signTransaction(tx);
```

## Sistema Anti-MEV e Sicurezza

- **Front-Running Protection**: Rilevamento e blocco attacchi front-running
- **Sandwich Attack Protection**: Prevenzione attacchi sandwich su AMM
- **Sniper Protection**: Blocco bot sniper su nuovi token
- **Fraud Detection**: Sistema scoring per indirizzi sospetti
- **Batch Transactions**: Transazioni batch con revert atomico

## Fee Structure

- **Master Fee**: 0.05% su ogni transazione → account master
- **Earning Opportunity**: Uguale per tutti i nodi onesti
- **Value per Task**: Scala con hardware (compute/storage/bandwidth)
- Più potenza = più guadagno per task, non più frequenza

## Architettura Fork

- **Fork Pubblici**: Devono connettersi al master per funzionare
- **Fork Privati**: Max 20 utenti, operano indipendentemente
- **Fee Distribuite**: 0.05% al master per ogni transazione sui fork

## Integrazioni DeFi (Pianificate)

Il sistema supporterà integrazione con i principali protocolli:
- Uniswap v2/v3/v4
- Sushiswap
- 1inch Aggregator
- Curve Finance
- 0x Protocol
- Cowswap
- Matcha
- Carbon (Bancor)
- YFinance (dati)

## Quick Start

```bash
# Clona il repository
git clone https://github.com/your-org/cloudchain.git
cd cloudchain

# Installa dipendenze
npm install

# Avvia nodo RPC
npm run node

# Crea wallet
npm run wallet:create

# Esegui test
npm test
```

## Configurazione

Crea un file `.env`:

```env
CHAIN_ID=1
NETWORK_ID=1
RPC_PORT=8545
MASTER_ADDRESS=0x...
IS_PRIVATE=false
MAX_PRIVATE_USERS=20
```

## Documentazione

- [Documentazione Completa](docs/)
- [Specifiche Borlang](borlang/spec.md)
- [Architettura Layer](layers/)
- [Guida Consensus](consensus/README.md)

## Stack Tecnologico

- **Runtime**: Node.js
- **Crypto**: Node.js crypto (AES-256-GCM, secp256k1)
- **Smart Contracts**: Borlang (compiler in sviluppo)
- **AI**: Ollama integration

## Licenza

Vedi [LICENSE](LICENSE) per i dettagli.

**Nota Importante**: Questa è una licenza open source con obbligo di documentazione delle modifiche. Tutte le modifiche devono essere documentate pubblicamente. Violazioni possono comportare sanzioni.

## Contribuire

Siamo alla ricerca di:

- 🔧 Sviluppatori Blockchain
- 🧠 Esperti AI/ML
- 🌐 Operatori Nodi
- 📝 Documentaristi
- 🧪 Beta Tester

Contribuisci con una pull request o contatta il team.

## Contatti

#Linkedin:

https://www.linkedin.com/in/lorenzo-leonardo-bortaccio-1314943ba?utm_source=share_via&utm_content=profile&utm_medium=member_android
---

<p align="center">
  <strong>⚠️ BETA VERSION - IN TESTING PHASE</strong><br>
  Seeking users, developers, and nodes to make it fully operational.
</p>

*CloudChain - The Future of Decentralized AI Computing*
