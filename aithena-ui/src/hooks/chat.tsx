//https://markus.oberlehner.net/blog/building-a-chatgpt-client-with-remix-leveraging-response-streaming-for-a-chat-like-experience/
import { useState } from "react";

type ChatMessage = Record<string, unknown>;

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const addMessage = (message: ChatMessage) =>
    setMessages((prevMessages: ChatMessage[]) => [...prevMessages, message]);

  return { messages, addMessage };
};
