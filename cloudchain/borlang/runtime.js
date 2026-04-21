class BorlangRuntime {
  constructor() {
    this.state = {}; // Contract state
    this.msg = { sender: null }; // Message context
    this.ollama = {
      // In a real implementation, this would call the Ollama API
      run: (model, input) => {
        // Placeholder: simulate Ollama response
        return `Ollama response for model ${model} with input: ${input}`;
      },
      load: (model) => {
        // Placeholder
        return `handle-${model}`;
      }
    };
  }

  // Set the message sender (called by the VM when invoking a function)
  setMsgSender(sender) {
    this.msg.sender = sender;
  }

  // Set a state variable
  setState(key, value) {
    this.state[key] = value;
  }

  // Get a state variable
  getState(key) {
    return this.state[key];
  }

  // Require function (throws if condition is false)
  require(condition, message) {
    if (!condition) {
      throw new Error(`Borlang runtime error: ${message}`);
    }
  }
}

module.exports = BorlangRuntime;