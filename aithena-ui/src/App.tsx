import "./App.css";
import {
  ChatMessage,
  ChatMessageProps,
  defaultChatMessageProps,
} from "./Components/ChatMessage";
import Sidebar from "./Components/Sidebar";
import { useState, useRef, useEffect, FormEvent } from "react";

interface MessageInfo {
  message: string;
  sender: string;
  time: string;
}

const defaultMessages: MessageInfo[] = [
  {
    message: "Hello!\nHow can I help you today?",
    sender: "Assistant",
    time: Date.now().toString(),
  },
];

let messages: MessageInfo[] = [...defaultMessages];

function App() {
  let [result, setResult] = useState<MessageInfo[]>(messages);
  let [text, setText] = useState<string>("");
  let [input, setInput] = useState("");
  let [loading, setLoading] = useState<boolean>(false);
  const abortControllerRef = useRef(new AbortController());
  const bottomRef = useRef<HTMLDivElement>(null);
  const [props, setProps] = useState<ChatMessageProps>(
    JSON.parse(localStorage.getItem("props") || "") || {
      ...defaultChatMessageProps,
    }
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [result, text]);

  useEffect(() => {
    console.log("Storing props to local storage");
    localStorage.setItem("props", JSON.stringify(props));
  }, [props]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    if (input === "") return;
    setLoading(true);
    try {
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

      let current = messages.length - 1;
      let text = "";

      const msgProps = { ...props, ["message"]: inputText };

      await ChatMessage(
        (data: any) => {
          if (data.choices) {
            console.log(data.choices[0].text);
            text = text + data.choices[0].text;
            messages[current].message = text;
            setText(text);
            setResult(messages);
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
            }
            console.log(data);
          }
        },
        msgProps,
        abortControllerRef.current.signal
      );
    } finally {
      console.log("Done");
      setLoading(false);
    }
  }

  function handleNewChatClick() {
    messages = [...defaultMessages];
    abortControllerRef.current.abort();
    setResult(messages);
    setLoading(false);
  }

  return (
    <>
      <div className="App">
        <aside className="sidebar">
          <div className="side-menu-button" onClick={handleNewChatClick}>
            <span>+</span>New Chat
          </div>
          <Sidebar props={props} setProps={setProps} />
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
                  <div className="message">
                    <span
                      dangerouslySetInnerHTML={{
                        __html: message.message.replace(/\n/g, "<br />"),
                      }}
                    />
                    {result.length - 1 === index && (
                      <span className="loading" hidden={!loading}>
                        ...
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={bottomRef}> </div>
          </div>
          <div className="chat-input-holder" onSubmit={handleSubmit}>
            <form>
              <input
                disabled={loading}
                className="chat-input-text-area"
                value={input}
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
