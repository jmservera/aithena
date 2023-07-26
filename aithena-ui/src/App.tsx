import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import { ChatMessage } from "./Components/ChatMessage";

import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
} from "@chatscope/chat-ui-kit-react";
import { MessageDirection } from "@chatscope/chat-ui-kit-react/src/types/unions";
import { useState, useRef, useEffect } from "react";

interface MessageInfo {
  message: string;
  sender: string;
  direction: MessageDirection;
  time: string;
}

function App() {
  // let [index, setIndex] = useState(-1);
  // let [messages, setMessages] = useState<string[]>([]);
  let [result, setResult] = useState("");
  const messagesRef = useRef<MessageInfo[]>([]);

  useEffect(() => {
    // this ensures that resultRef.current is up to date during each render
  }, [result]);

  return (
    <>
      <button
        onClick={async () => {
          let direction: MessageDirection = "incoming";
          let sender = "Assistant";
          if (Math.random() > 0.5) {
            sender = "User";
            direction = "outgoing";
          }
          messagesRef.current.push({
            message: "",
            sender: sender,
            direction: direction,
            time: Date.now().toString(),
          });
          let current = messagesRef.current.length - 1;
          let text = "";

          ChatMessage((data: any) => {
            if (data.choices) {
              text = text + data.choices[0].text;
              messagesRef.current[current].message = text;
              setResult(text);
            } else {
              if (data.messages) {
                data.messages.forEach((message: any) => {
                  text =
                    text +
                    `<b>Path</b>: ${message.path}, page ${message.page}\n<b>Text</b>: ${message.payload}\n`;
                });
                text = text + "\n<b>Summary</b>: ";
              }
              console.log("Other data");
              console.log(data);
            }
          }, "Hello, how are you doing today? Can you tell me about yourself?");
        }}
      >
        Click me
      </button>
      <div style={{ position: "relative", height: "500px" }}>
        <MainContainer>
          <ChatContainer>
            <MessageInput placeholder="Type your message here" />
            <MessageList>
              {messagesRef.current.map((message, index) => (
                <Message
                  key={index}
                  model={{
                    message: message.message,
                    sentTime: "just now",
                    sender: message.sender,
                    direction: message.direction,
                    position:
                      messagesRef.current.length === 1
                        ? "single"
                        : index === 0
                        ? "first"
                        : index === messagesRef.current.length - 1
                        ? "last"
                        : "normal",
                  }}
                />
              ))}
            </MessageList>
          </ChatContainer>
        </MainContainer>
      </div>
    </>
  );
}

export default App;
