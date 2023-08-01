import "./App.css";
// import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import { ChatMessage } from "./Components/ChatMessage";
import { useState, useRef, useEffect, FormEvent } from "react";
// import useGlobalEvent from "beautiful-react-hooks/useGlobalEvent";
// import useDebouncedCallback from "beautiful-react-hooks/useDebouncedCallback";

interface MessageInfo {
  message: string;
  sender: string;
  time: string;
}

// const messages: MessageInfo[] = [
//   {
//     message: "How can I help you today?",
//     sender: "Assistant",
//     time: Date.now().toString(),
//   },
// ];

function App() {
  let [result, setResult] = useState("");
  let [input, setInput] = useState("");
  const messagesRef = useRef<MessageInfo[]>([
    {
      message: "How can I help you today?",
      sender: "Assistant",
      time: Date.now().toString(),
    },
  ]);

  // useEffect(() => {
  //   // this ensures that resultRef.current is up to date during each render
  // }, [result]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (input === "") return;
    const inputText = input;
    messagesRef.current.push(
      {
        message: inputText,
        sender: "User",
        time: Date.now().toString(),
      },
      {
        message: "",
        sender: "Assistant",
        time: Date.now().toString(),
      }
    );
    setResult(inputText);
    setInput("");

    let current = messagesRef.current.length - 1;
    let text = "";

    await ChatMessage((data: any) => {
      if (data.choices) {
        console.log(`Choices ${current} ${text}`);
        text = text + data.choices[0].text;
        messagesRef.current[current].message = text;
        setResult(text);
      } else {
        if (data.messages) {
          console.log("Other data");
          text = "The following information was found:\n";
          data.messages.forEach((message: any) => {
            text =
              text +
              `<b>Document</b> (${Math.round(
                message.score * 100
              )}% similarity): ${message.path}, page ${
                message.page
              }\n<b>Text</b>: ${message.payload}\n`;
          });
          text = text + "\n<b>Summary</b>: ";
          console.log(`Summary ${current} ${text}`);
          messagesRef.current[current].message = text;
          setResult(text);
        }
        console.log(data);
      }
    }, inputText);
  }

  return (
    <>
      <div className="App">
        <aside className="sidebar">
          <div className="side-menu-button">
            <span>+</span>New Chat
          </div>
        </aside>
        <section className="chatbox">
          <div className="chat-log">
            {messagesRef.current.map((message, index) => (
              <div
                key={index}
                className={`chat-message ${
                  message.sender === "Assistant" && "chatgpt"
                }`}
              >
                <div className="chat-message-center">
                  <div
                    className={`avatar ${
                      message.sender === "Assistant" && "chatgpt"
                    }`}
                  >
                    {message.sender === "User" ? "👤" : "🤖"}
                  </div>
                  <div
                    className="message"
                    dangerouslySetInnerHTML={{
                      __html: message.message.replace(/\n/g, "<br />"),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="chat-input-holder" onSubmit={handleSubmit}>
            <form>
              <input
                className="chat-input-text-area"
                placeholder="Type your message here"
                onChange={(e) => setInput(e.target.value)}
              ></input>
            </form>
          </div>
        </section>
      </div>
    </>
  );
}

export default App;
