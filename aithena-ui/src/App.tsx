import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import { ChatMessage } from "./Components/ChatMessage";

import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
} from "@chatscope/chat-ui-kit-react";
import { useState } from "react";

function App() {
  let [index, setIndex] = useState(-1);
  let [messages, setMessages] = useState<string[]>([]);

  return (
    <>
      <button
        onClick={() => {
          let idx = index + 1;
          let intermediate = `Answer: `;
          setIndex(idx);
          let msgs = [...messages];
          msgs.push(intermediate);

          ChatMessage((data: any) => {
            console.log(`setting ${data()}`);
            intermediate = intermediate + data();
            msgs[idx] = intermediate;
            setMessages(msgs);
          }, "Hello");
        }}
      >
        Click me
      </button>
      <div style={{ position: "relative", height: "500px" }}>
        <MainContainer>
          <ChatContainer>
            <MessageInput placeholder="Type your message here" />
            <MessageList>
              {messages.map((message) => (
                <Message
                  model={{
                    message: message,
                    sentTime: "just now",
                    sender: "Joe",
                    direction: "incoming",
                    position: "first",
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
