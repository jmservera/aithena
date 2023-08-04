import { fetchEventSource } from "@microsoft/fetch-event-source";
import {
  CreateCompletionRequest,
  defaultCreateCompletionRequest,
} from "./types/CreateCompletionRequest";

const serverBaseURL = `${import.meta.env.VITE_API_URL}/v1/question/`;
console.log(`serverBaseURL: ${serverBaseURL}`);

type MessageHandler = (data: any) => void;

export type ChatMessageProps = {
  message: string;
  limit?: number;
  model_properties: CreateCompletionRequest;
};

export const defaultChatMessageProps: ChatMessageProps = {
  message: "",
  limit: 8,
  model_properties: defaultCreateCompletionRequest,
};

export const ChatMessage = async (
  onEvent: MessageHandler,
  messageProps: ChatMessageProps,
  signal: AbortSignal
) => {
  const { message, limit = 12, model_properties } = messageProps;
  model_properties.stream = true;
  console.log(`message limit: ${limit}`);

  console.log(`fetching ${message}`);
  let msg = JSON.stringify({
    input: message,
    limit: limit,
    model_properties: {
      stream: model_properties.stream,
      max_tokens: model_properties.max_tokens,
      temperature: model_properties.temperature,
    },
  });
  console.log(`input: ${msg}`);

  await fetchEventSource(`${serverBaseURL}`, {
    signal: signal,
    openWhenHidden: true, // https://github.com/Azure/fetch-event-source/issues/17
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      "X-Accel-Buffering": "no",
    },
    body: msg,
    async onopen(res) {
      if (res.ok && res.status === 200) {
        console.log("Connection made ", res);
      } else if (res.status >= 400 && res.status < 500 && res.status !== 429) {
        console.log("Client-side error ", res);
      }
    },
    onmessage(event) {
      if (onEvent === undefined) return;
      try {
        if (event.data.trim() !== "") {
          const parsedData = JSON.parse(event.data);
          onEvent(parsedData);
        }
      } catch (e) {
        console.log(e);
        console.log(`|${JSON.stringify(event.data)}| is not a valid JSON`);
      }
    },
    onclose() {
      console.log("Connection closed by the server");
    },
    onerror(err) {
      console.log("There was an error from server", err);
    },
  });
};
