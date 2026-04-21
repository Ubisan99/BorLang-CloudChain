# Borlang

<p align="center">
  <img src="https://img.shields.io/badge/Language-Smart%20Contract-blue?style=for-the-badge" alt="Language">
  <img src="https://img.shields.io/badge/Version-Beta-yellow?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Purpose-AI%20Blockchain-purple?style=for-the-badge" alt="Purpose">
</p>

> ⚠️ **VERSIONE BETA** - Linguaggio per smart contract in fase di sviluppo.

Borlang è un linguaggio di programmazione per smart contract progettato specificamente per **CloudChain**, con primitivi AI nativi e supporto per distribuzione legale di file open-source.

## Caratteristiche Principali

### Primitivi AI Nativi
- Funzioni built-in per inferenza Ollama
- Supporto per modelli AI on-chain
- Tokenizzazione automatica
- Batch AI processing

### Distribuzione File Legale
- Verifica licenze OSI-approved
- Content addressing (IPFS-like)
- Anti-pirateria integrata
- Solo file open-source legal

### Sicurezza
- Execution environment deterministico
- Sandbox isolato
- Resource limits
- Revert automatico su errori

## Sintassi

### Hello World

```borlang
contract HelloWorld {
    pub fn greet(name: str) -> str {
        return "Ciao, " + name + "!";
    }
}
```

### Smart Contract con AI

```borlang
contract AIBot {
    pub fn ask_model(prompt: str) -> str {
        // Chiamata diretta a Ollama
        return ai::infer("llama2", prompt);
    }
    
    pub fn batch_infer(prompts: list<str>) -> list<str> {
        // Elaborazione batch
        return ai::batch_infer("llama2", prompts);
    }
}
```

### Distribuzione File Legale

```borlang
contract FileRegistry {
    pub fn register_file(hash: str, license: str) -> bool {
        // Verifica licenza OSI-approved
        require(legal::is_approved(license), "Licenza non approvata");
        
        // Registra file con content address
        legal::register(hash, license);
        return true;
    }
    
    pub fn verify_file(hash: str) -> bool {
        return legal::verify(hash);
    }
}
```

## Tipi di Dato

| Tipo | Descrizione |
|------|-------------|
| `u8`, `u16`, `u32`, `u64` | Interi unsigned |
| `i8`, `i16`, `i32`, `i64` | Interi signed |
| `bool` | Booleano |
| `str` | Stringa |
| `addr` | Indirizzo wallet (0x...) |
| `list<T>` | Lista generica |
| `map<K, V>` | Mappa chiave-valore |

## Funzioni Built-in

### AI (`ai::`)
```borlang
ai::infer(model: str, prompt: str) -> str
ai::batch_infer(model: str, prompts: list<str>) -> list<str>
ai::tokenize(text: str) -> list<u32>
ai::detokenize(tokens: list<u32>) -> str
```

### Legal (`legal::`)
```borlang
legal::is_approved(license: str) -> bool
legal::register(hash: str, license: str) -> bool
legal::verify(hash: str) -> bool
legal::get_license(hash: str) -> str
```

### Crypto (`crypto::`)
```borlang
crypto::sha256(data: str) -> str
crypto::keccak256(data: str) -> str
crypto::verify_sig(msg: str, sig: str, pubkey: str) -> bool
```

### Storage (`storage::`)
```borlang
storage::put(key: str, value: any) -> bool
storage::get(key: str) -> any
storage::delete(key: str) -> bool
storage::exists(key: str) -> bool
```

## Compilazione

```bash
# Compila un file .borlang
npm run compile -- input.borlang

# Output: bytecode.json
```

## Roadmap

- [ ] Compiler completo
- [ ] Runtime VM
- [ ] Debugger
- [ ] IDE Extension
- [ ] Testnet deployment

## License

Vedi [LICENSE](LICENSE).

**Nota**: Questo linguaggio è parte di CloudChain. Modifiche devono essere documentate.

---

<p align="center">
  <strong>⚠️ BETA VERSION</strong><br>
  Smart contract language for CloudChain
</p>

*Borlang - Smart Contracts for Decentralized AI*