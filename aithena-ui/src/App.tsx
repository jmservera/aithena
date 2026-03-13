import "./App.css";
import {
  ChatMessage,
  ChatMessageProps,
  defaultChatMessageProps,
} from "./Components/ChatMessage";
import Configbar from "./Components/Configbar";
import UploadDialog from "./Components/UploadDialog";
import { useState, useRef, useEffect, FormEvent } from "react";

interface MessageInfo {
  message: string;
  sender: string;
  time: string;
}

interface SearchResultMessage {
  score: number;
  path: string;
  page: number;
  payload: string;
}

interface CompletionData {
  choices?: { text: string }[];
  messages?: SearchResultMessage[];
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
  const [result, setResult] = useState<MessageInfo[]>(messages);
  const [text, setText] = useState<string>("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState<boolean>(false);
  const [showUpload, setShowUpload] = useState(false);
  const abortControllerRef = useRef(new AbortController());
  const bottomRef = useRef<HTMLDivElement>(null);
  const [props, setProps] = useState<ChatMessageProps>(
    JSON.parse(localStorage.getItem("props") || "null") || {
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

      const current = messages.length - 1;
      let responseText = "";

      const msgProps = { ...props, message: inputText };

      await ChatMessage(
        (data: CompletionData) => {
          if (data.choices) {
            console.log(data.choices[0].text);
            responseText = responseText + data.choices[0].text;
            messages[current].message = responseText;
            setText(responseText);
            setResult(messages);
          } else {
            if (data.messages) {
              console.log("Other data");
              responseText = "The following information was found:\n";
              data.messages.forEach((message: SearchResultMessage) => {
                responseText =
                  responseText +
                  `<b>Document</b> (${Math.round(
                    message.score * 100
                  )}% similarity): ${message.path}, page ${
                    message.page
                  }\n<b>Text</b>: ${message.payload}\n`;
              });
              responseText = responseText + "\n<b>Summary</b>: ";
              console.log(`Summary ${current} ${responseText}`);
              messages[current].message = responseText;
              setResult(messages);
              setText(responseText);
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

  function handleSearchBook(query: string) {
    setInput(query);
    setShowUpload(false);
  }

  return (
    <>
      <div className="App">
        <aside className="sidebar">
          <Configbar props={props} setProps={setProps} />
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
              <div
                className="swipe-button"
                title="New Chat"
                onClick={handleNewChatClick}
              >
                🧹
              </div>
              <input
                disabled={loading}
                className="chat-input-text-area"
                value={input}
                placeholder="Type your message here"
                onChange={(e) => setInput(e.target.value)}
              ></input>
              <button
                type="button"
                className="upload-trigger-btn"
                title="Upload a PDF book"
                onClick={() => setShowUpload(true)}
                disabled={loading}
              >
                📤 Upload PDF
              </button>
            </form>
          </div>
        </section>
      </div>

      {showUpload && (
        <UploadDialog
          onClose={() => setShowUpload(false)}
          onSearchBook={handleSearchBook}
        />
      )}
    </>
  );
}

export default App;
