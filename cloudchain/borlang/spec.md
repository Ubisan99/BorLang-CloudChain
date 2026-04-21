# Borlang Smart Contract Language

Borlang is a statically-typed, purpose-built smart contract language for CloudChain, designed for security, simplicity, and native AI compute integration.

## Design Goals

1. **Security First**: Built-in protection against common vulnerabilities (reentrancy, overflow, etc.)
2. **AI-Native**: First-class support for invoking Ollama models and handling tensor data
3. **Deterministic**: All operations must be deterministic for consensus
4. **Gas-Efficient**: Optimized for low gas consumption on CloudChain
5. **Simple Syntax**: Easy to learn for developers familiar with Go/Rust

## Language Overview

### Basic Syntax

```borlang
// Define a contract
contract AiModelManager {
    // State variables
    modelId: string;
    owner: address;
    
    // Constructor
    init(modelId: string) {
        self.modelId = modelId;
        self.owner = msg.sender;
    }
    
    // Public function
    pub fn infer(input: string) -> string {
        require(msg.sender == self.owner, "Unauthorized");
        let result = ollama.run(self.modelId, input);
        return result;
    }
}
```

### Types

- **Primitive**: `bool`, `int`, `uint`, `float`, `string`, `address`, `bytes`
- **Composite**: `struct`, `array[T]`, `map[K,V]`
- **Special**: `tensor` (for AI data), `model_handle` (reference to Ollama model)

### Keywords

- `contract`: Define a smart contract
- `init`: Constructor function
- `pub`: Public function (callable externally)
- `priv`: Private function (internal only)
- `require`: Condition check (reverts if false)
- `ollama`: Built-in module for AI operations
- `log`: Event logging

### Ollama Integration

```borlang
// Load a model (once per contract deployment)
let handle = ollama.load("llama2");

// Run inference
let result = ollama.run(handle, "What is 2+2?");

// Check model status
let status = ollama.status(handle);
```

### Control Flow

- `if/else` conditional
- `for` loop (with bounded iterations for determinism)
- `match` pattern matching (enums)

### Events

```borlang
event ModelLoaded(modelId: string);
event InferenceCompleted(input: string, output: string);

// Emit an event
log ModelLoaded({modelId: "llama2"});
```

### Safety Features

- No pointer arithmetic
- Automatic bounds checking on arrays
- Overflow checking on integers
- Reentrancy guards via mutex pattern
- Deterministic execution (no randomness without explicit seed)

## File Structure

- `spec.md`: This specification
- `stdlib/`: Standard library functions
- `compiler/`: Borlang to WASM compiler (placeholder)
- `vm/`: Borlang virtual machine implementation (placeholder)

## Example Contracts

See `examples/` directory for:
- AI model marketplace
- Decentralized autonomous organization (DAO)
- Federated learning coordinator