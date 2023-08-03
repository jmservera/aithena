import React from "react";
import {
  ChatMessageProps,
  defaultChatMessageProps,
  CreateCompletionRequest,
} from "./ChatMessage";

const CreateCompletionRequestDef = [
  {
    key: "max_tokens",
    type: "number",
    min: 1,
    max: 8192,
    default: 16,
    increment: 1,
    desc: "The maximum number of tokens to generate.",
  },
  {
    key: "temperature",
    type: "number",
    min: 0,
    max: 2,
    default: 0.8,
    increment: 0.1,
    desc: "Adjust the randomness of the generated text. Temperature is a hyperparameter that controls the randomness of the generated text. It affects the probability distribution of the model's output tokens. A higher temperature (e.g., 1.5) makes the output more random and creative, while a lower temperature (e.g., 0.5) makes the output more focused, deterministic, and conservative. The default value is 0.8, which provides a balance between randomness and determinism. At the extreme, a temperature of 0 will always pick the most likely next token, leading to identical outputs in each run.",
  },
  {
    key: "top_p",
    type: "number",
    min: 0,
    max: 1,
    default: 0.95,
    increment: 0.05,
    desc: "Limit the next token selection to a subset of tokens with a cumulative probability above a threshold P.\nTop-p sampling, also known as nucleus sampling, is another text generation method that selects the next token from a subset of tokens that together have a cumulative probability of at least p. This method provides a balance between diversity and quality by considering both the probabilities of tokens and the number of tokens to sample from. A higher value for top_p (e.g., 0.95) will lead to more diverse text, while a lower value (e.g., 0.5) will generate more focused and conservative text.",
  },
  {
    key: "mirostat_mode",
    type: "number",
    min: 0,
    max: 2,
    default: 0,
    increment: 1,
    desc: "Enable Mirostat constant-perplexity algorithm of the specified version (1 or 2; 0 = disabled)",
  },
  {
    key: "mirostat_tau",
    type: "number",
    min: 0,
    max: 10,
    default: 5,
    increment: 0.1,
    desc: "Mirostat target entropy, i.e. the target perplexity - lower values produce focused and coherent text, larger values produce more diverse and less coherent text",
  },
  {
    key: "mirostat_eta",
    type: "number",
    min: 0.001,
    max: 1,
    default: 0.1,
    increment: 0.001,
    desc: "Mirostat learning rate",
  },
  {
    key: "echo",
    type: "boolean",
    default: false,
    desc: "Whether to echo the prompt in the generated text. Useful for chatbots.",
  },
  {
    key: "stream",
    type: "boolean",
    default: false,
    desc: "Whether to stream the results as they are generated. Useful for chatbots.",
  },
  // {
  //   key: "logprobs",
  //   type: "number",
  //   min: 0,
  //   default: null,
  // },
  {
    key: "presence_penalty",
    type: "number",
    def: 0,
    desc: "Positive values penalize new tokens based on whether they appear in the text so far, increasing the model's likelihood to talk about new topics.",
  },
  {
    key: "frequency_penalty",
    type: "number",
    def: 0,
    desc: "Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim.",
  },
  {
    key: "logit_bias",
    type: "object",
  },
  {
    key: "n",
    type: "number",
    def: 1,
  },
  {
    key: "best_of",
    type: "integer",
    def: 1,
  },
  {
    key: "top_k",
    type: "number",
    def: 40,
    min: 0,
    max: 500,
    desc: "Limit the next token selection to the K most probable tokens. Top-k sampling is a text generation method that selects the next token only from the top k most likely tokens predicted by the model. It helps reduce the risk of generating low-probability or nonsensical tokens, but it may also limit the diversity of the output. A higher value for top_k (e.g., 100) will consider more tokens and lead to more diverse text, while a lower value (e.g., 10) will focus on the most probable tokens and generate more conservative text.",
  },
  {
    key: "repeat_penalty",
    type: "number",
    def: 1.1,
    min: 0,
    max: 5,
    increment: 1.1,
  },
];

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

  const renderPropertyEditor = (value: any, index: number) => {
    if (value.type == "number") {
      return (
        <>
          <label htmlFor={value.key}>{value.key}:</label>
          <input
            key={index}
            type="range"
            title={value.desc}
            id={value.key}
            name={value.key}
            min={value.min}
            max={value.max}
            step={value.increment}
            value={props.model_properties[
              value.key as keyof CreateCompletionRequest
            ]?.toString()}
            onChange={handleModelChange}
          />
          <span>
            {props.model_properties[value.key as keyof CreateCompletionRequest]}
          </span>
          <br />
        </>
      );
    }
  };

  return (
    <div>
      <h1>Config</h1>
      <label htmlFor="limit">limit:</label>
      <input
        title="The maximum number of results to generate."
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
      {CreateCompletionRequestDef.map((value, index) =>
        renderPropertyEditor(value, index)
      )}
      <div className="side-menu-button" onClick={handleResetClick}>
        <span>🧹</span>Reset
      </div>
    </div>
  );
};

export default Sidebar;
