import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import { ChatMessage } from "./Components/ChatMessage";

import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
} from "@chatscope/chat-ui-kit-react";
import { useState, useRef, useEffect } from "react";

function App() {
  // let [index, setIndex] = useState(-1);
  // let [messages, setMessages] = useState<string[]>([]);
  let [result, setResult] = useState<string | undefined>("");
  const resultRef = useRef<string>();

  useEffect(() => {
    // this ensures that resultRef.current is up to date during each render
    resultRef.current = result;
  }, [result]);

  return (
    <>
      <button
        onClick={async () => {
          // let idx = index + 1;
          // setIndex(idx);
          // let msgs = [...messages];
          // msgs.push(result);

          ChatMessage((data: any) => {
            console.log(`setting ${data()}`);
            resultRef.current = resultRef.current + data();
            setResult(resultRef.current);
            // msgs[idx] = intermediate;
            // setMessages(msgs);
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
              {/* {messages.map((message) => ( */}
              <Message
                model={{
                  message: result,
                  sentTime: "just now",
                  sender: "Joe",
                  direction: "incoming",
                  position: "first",
                }}
              />
              {/* ))} */}
            </MessageList>
          </ChatContainer>
        </MainContainer>
      </div>
    </>
  );
}

export default App;
