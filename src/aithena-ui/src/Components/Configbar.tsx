import React from 'react';
import { useIntl } from 'react-intl';

import { ChatMessageProps, defaultChatMessageProps } from './ChatMessage';

import {
  CreateCompletionRequest,
  CreateCompletionRequestDef,
  CreateCompletionRequestField,
} from './types/CreateCompletionRequest';

const Configbar = ({
  props,
  setProps,
}: {
  props: ChatMessageProps;
  setProps: React.Dispatch<React.SetStateAction<ChatMessageProps>>;
}) => {
  const intl = useIntl();

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

  const renderPropertyEditor = (value: CreateCompletionRequestField, index: number) => {
    if (value.type === 'number') {
      return (
        <>
          <label key={`label-${index}`} htmlFor={value.key}>
            {value.key}:
          </label>
          <input
            key={`input-${index}`}
            disabled={index > 1}
            type="range"
            title={value.desc}
            id={value.key}
            name={value.key}
            min={value.min}
            max={value.max}
            step={value.increment}
            value={props.model_properties[value.key as keyof CreateCompletionRequest]?.toString()}
            onChange={handleModelChange}
          />
          <span key={`span-${index}`}>
            {props.model_properties[value.key as keyof CreateCompletionRequest]}
          </span>
          <br key={`br-${index}`} />
        </>
      );
    }

    return null;
  };

  return (
    <div>
      <h1>{intl.formatMessage({ id: 'config.title' })}</h1>
      <label key="limit-label" htmlFor="limit">
        {intl.formatMessage({ id: 'config.limit' })}
      </label>
      <input
        key="limit-input"
        title={intl.formatMessage({ id: 'config.limitDescription' })}
        type="range"
        id="limit"
        name="limit"
        min="1"
        max="9"
        value={props.limit}
        onChange={handleChange}
      />
      <span key="limit-span">{props.limit}</span>
      <br key="limit-br" />
      {CreateCompletionRequestDef.map((value, index) => renderPropertyEditor(value, index))}
      <button key="side-key" type="button" className="side-menu-button" onClick={handleResetClick}>
        <span aria-hidden="true">🧹</span> {intl.formatMessage({ id: 'config.reset' })}
      </button>
    </div>
  );
};

export default Configbar;
