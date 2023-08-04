import React from "react";
import { ChatMessageProps, defaultChatMessageProps } from "./ChatMessage";

import {
  CreateCompletionRequest,
  CreateCompletionRequestDef,
} from "./types/CreateCompletionRequest";

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
