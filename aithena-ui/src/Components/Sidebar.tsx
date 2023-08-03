import React from "react";
import { ChatMessageProps, defaultChatMessageProps } from "./ChatMessage";

// Define a component for the sidebar
const Sidebar = ({
  props,
  setProps,
}: {
  props: ChatMessageProps;
  setProps: React.Dispatch<React.SetStateAction<ChatMessageProps>>;
}) => {
  // Handle input changes and update the props state
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setProps((prevProps) => ({ ...prevProps, [name]: value }));
  };

  const handleModelChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setProps((prevProps) => ({
      ...prevProps,
      model_properties: { ...prevProps.model_properties, [name]: value },
    }));
  };

  const handleResetClick = () => {
    setProps({ ...defaultChatMessageProps });
  };

  return (
    <div>
      <h1>Config</h1>
      <label htmlFor="limit">Query Results Limit:</label>
      <input
        type="range"
        id="limit"
        name="limit"
        min="1"
        max="25"
        value={props.limit}
        onChange={handleChange}
      />
      <span>{props.limit}</span>
      <br />
      {/* input for max_tokens */}
      <label htmlFor="max_tokens">max_tokens:</label>
      <input
        title="The maximum number of tokens to generate."
        type="range"
        id="max_tokens"
        name="max_tokens"
        min="10"
        max="8192"
        value={props.model_properties.max_tokens}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.max_tokens}</span>
      <br />
      {/* input for temperature */}
      <label htmlFor="temperature">temperature:</label>
      <input
        title="Adjust the randomness of the generated text. Temperature is a hyperparameter that controls the randomness of the generated text. It affects the probability distribution of the model's output tokens. A higher temperature (e.g., 1.5) makes the output more random and creative, while a lower temperature (e.g., 0.5) makes the output more focused, deterministic, and conservative. The default value is 0.8, which provides a balance between randomness and determinism. At the extreme, a temperature of 0 will always pick the most likely next token, leading to identical outputs in each run."
        type="range"
        id="temperature"
        name="temperature"
        min="0"
        max="3"
        step="0.01"
        value={props.model_properties.temperature}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.temperature}</span>
      <br />
      {/* input for top_p */}
      <label htmlFor="top_p">top_p:</label>
      <input
        title="Limit the next token selection to a subset of tokens with a cumulative probability above a threshold P.\n\nTop-p sampling, also known as nucleus sampling, is another text generation method that selects the next token from a subset of tokens that together have a cumulative probability of at least p. This method provides a balance between diversity and quality by considering both the probabilities of tokens and the number of tokens to sample from. A higher value for top_p (e.g., 0.95) will lead to more diverse text, while a lower value (e.g., 0.5) will generate more focused and conservative text."
        type="range"
        id="top_p"
        name="top_p"
        min="0"
        max="1"
        step="0.01"
        value={props.model_properties.top_p}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.top_p}</span>
      <br />
      {/* input for mirostat_mode */}
      <label htmlFor="mirostat_mode">mirostat_mode:</label>
      <input
        title="Enable Mirostat constant-perplexity algorithm of the specified version (1 or 2; 0 = disabled)"
        type="range"
        id="mirostat_mode"
        name="mirostat_mode"
        min="0"
        max="2"
        value={props.model_properties.mirostat_mode}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.mirostat_mode}</span>
      <br />
      {/* input for mirostat_tau */}
      <label htmlFor="mirostat_tau">mirostat_tau:</label>
      <input
        title="Mirostat target entropy, i.e. the target perplexity - lower values produce focused and coherent text, larger values produce more diverse and less coherent text"
        type="range"
        id="mirostat_tau"
        name="mirostat_tau"
        min="0"
        max="10"
        step="0.1"
        value={props.model_properties.mirostat_tau}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.mirostat_tau}</span>
      <br />
      {/* input for mirostat_eta */}
      <label htmlFor="mirostat_eta">mirostat_eta:</label>
      <input
        title="Mirostat learning rate"
        type="range"
        id="mirostat_eta"
        name="mirostat_eta"
        min="0.001"
        max="1"
        step="0.001"
        value={props.model_properties.mirostat_eta}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.mirostat_eta}</span>
      <br />
      {/* input for presence_penalty */}
      <label htmlFor="presence_penalty">presence_penalty:</label>
      <input
        title="Positive values penalize new tokens based on whether they appear in the text so far, increasing the model's likelihood to talk about new topics."
        type="range"
        id="presence_penalty"
        name="presence_penalty"
        min="-2"
        max="2"
        step="0.1"
        value={props.model_properties.presence_penalty}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.presence_penalty}</span>
      <br />
      {/* input for frequency_penalty */}
      <label htmlFor="frequency_penalty">frequency_penalty:</label>
      <input
        title="Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim."
        type="range"
        id="frequency_penalty"
        name="frequency_penalty"
        min="-2"
        max="2"
        step="0.1"
        value={props.model_properties.frequency_penalty}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.frequency_penalty}</span>
      <br />
      {/* input for n */}
      <label htmlFor="n">n:</label>
      <input
        title="N"
        type="range"
        id="n"
        name="n"
        min="1"
        max="5"
        value={props.model_properties.n}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.n}</span>
      <br />
      {/* input for best_of */}
      <label htmlFor="best_of">best_of:</label>
      <input
        title="Best Of"
        type="range"
        id="best_of"
        name="best_of"
        min="1"
        max="10"
        value={props.model_properties.best_of}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.best_of}</span>
      <br />
      {/* input for top_k */}
      <label htmlFor="top_k">top_k:</label>
      <input
        title="Limit the next token selection to the K most probable tokens.\n\nTop-k sampling is a text generation method that selects the next token only from the top k most likely tokens predicted by the model. It helps reduce the risk of generating low-probability or nonsensical tokens, but it may also limit the diversity of the output. A higher value for top_k (e.g., 100) will consider more tokens and lead to more diverse text, while a lower value (e.g., 10) will focus on the most probable tokens and generate more conservative text."
        type="range"
        id="top_k"
        name="top_k"
        min="0"
        max="100"
        value={props.model_properties.top_k}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.top_k}</span>
      {/* input for repeat_penalty */}
      <label htmlFor="repeat_penalty">repeat_penalty:</label>
      <input
        title="A penalty applied to each token that is already generated. This helps prevent the model from repeating itself.\n\nRepeat penalty is a hyperparameter used to penalize the repetition of token sequences during text generation. It helps prevent the model from generating repetitive or monotonous text. A higher value (e.g., 1.5) will penalize repetitions more strongly, while a lower value (e.g., 0.9) will be more lenient."
        type="range"
        id="repeat_penalty"
        name="repeat_penalty"
        min="0"
        max="5"
        step="0.1"
        value={props.model_properties.repeat_penalty}
        onChange={handleModelChange}
      />
      <span>{props.model_properties.repeat_penalty}</span>
      <br />
      <div className="side-menu-button" onClick={handleResetClick}>
        <span>🧹</span>Reset
      </div>
    </div>
  );
};

export default Sidebar;
