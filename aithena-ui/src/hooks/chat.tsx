//https://markus.oberlehner.net/blog/building-a-chatgpt-client-with-remix-leveraging-response-streaming-for-a-chat-like-experience/
import { useState } from "react";

export const useChat = () => {
  const [messages, setMessages] = useState<any>([]);

  const addMessage = (message: any) =>
    setMessages((prevMessages: any) => [...prevMessages, message]);

  return { messages, addMessage };
};
