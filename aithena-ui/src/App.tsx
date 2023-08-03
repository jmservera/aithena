import "./App.css";
import { ChatMessage, ChatMessageProps } from "./Components/ChatMessage";
import Sidebar from "./Components/Sidebar";
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
  let [loading, setLoading] = useState<boolean>(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [props, setProps] = useState<ChatMessageProps>({
    message: "",
    limit: 12,
    model_properties: {
      max_tokens: 1200,
      temperature: 0.5,
      top_p: 0.95,
      mirostat_mode: 0,
      mirostat_tau: 5,
      mirostat_eta: 0.1,
      echo: false,
      stream: true,
      presence_penalty: 0,
      frequency_penalty: 0,
      n: 1,
      best_of: 1,
      top_k: 40,
      repeat_penalty: 1.1,
    },
  });

  const scrollToBottom = () =>
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => {
    // this ensures that resultRef.current is up to date during each render
    scrollToBottom();
  }, [result, text]);

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

      await ChatMessage((data: any) => {
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
      }, msgProps);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="App">
        <aside className="sidebar">
          <div className="side-menu-button">
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
