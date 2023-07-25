import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";

import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
} from "@chatscope/chat-ui-kit-react";

function App() {
  return (
    <div style={{ position: "relative", height: "500px" }}>
      <MainContainer>
        <ChatContainer>
          <MessageList>
            <Message
              model={{
                message: "Hello my friend",
                sentTime: "just now",
                sender: "Joe",
                direction: "incoming",
                position: "first",
              }}
            />
            <Message
              model={{
                message: "Hello my friend",
                sentTime: "1 hour ago",
                sender: "Joe",
                direction: "incoming",
                position: "last",
              }}
            />
          </MessageList>
          <MessageInput placeholder="Type message here" />
        </ChatContainer>
      </MainContainer>
    </div>
  );
}

export default App;
