import "./App.css";
// import "bootstrap/dist/css/bootstrap.min.css";

import { ChatMessage } from "./Components/ChatMessage";
import { useState, useRef, useEffect, FormEvent } from "react";

interface MessageInfo {
  message: string;
  sender: string;
  time: string;
}

const messages: MessageInfo[] = [
  {
    message: "Hello!\nHow can I help you today?",
    sender: "Assistant",
    time: Date.now().toString(),
  },
];

function App() {
  let [result, setResult] = useState<MessageInfo[]>(messages);
  let [text, setText] = useState<string>("");
  let [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () =>
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => {
    // this ensures that resultRef.current is up to date during each render
  }, [result, text]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (input === "") return;
    const inputText = input;
    messages.push(
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
    setResult(messages);
    setText(inputText);
    setInput("");
    scrollToBottom();

    let current = messages.length - 1;
    let text = "";

    await ChatMessage((data: any) => {
      if (data.choices) {
        console.log(`Choices ${current} ${text}`);
        text = text + data.choices[0].text;
        messages[current].message = text;
        setText(text);
        setResult(messages);
        scrollToBottom();
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
          messages[current].message = text;
          setResult(messages);
          setText(text);
          scrollToBottom();
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
            {result.map((message, index) => (
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
            <div ref={bottomRef}> </div>
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
