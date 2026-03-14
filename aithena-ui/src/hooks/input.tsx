import { useState } from "react";

export const useInput = () => {
  const [input, setInput] = useState("");

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) =>
    setInput(event.target.value);
  const resetInput = () => setInput("");

  return { input, handleInputChange, resetInput };
};
