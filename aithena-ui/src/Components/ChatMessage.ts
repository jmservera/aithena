import { fetchEventSource } from "@microsoft/fetch-event-source";

import { buildApiUrl } from "../api";
import {
  CreateCompletionRequest,
  defaultCreateCompletionRequest,
} from "./types/CreateCompletionRequest";

const serverBaseURL = buildApiUrl("/v1/question/");

type MessageHandler = (data: unknown) => void;

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

export async function ChatMessage(
  onEvent: MessageHandler,
  messageProps: ChatMessageProps,
  signal: AbortSignal
): Promise<void> {
  const { message, limit = 12, model_properties } = messageProps;
  const requestModelProperties = { ...model_properties, stream: true };
  const msg = JSON.stringify({
    input: message,
    limit,
    model_properties: {
      stream: requestModelProperties.stream,
      max_tokens: requestModelProperties.max_tokens,
      temperature: requestModelProperties.temperature,
    },
  });

  await fetchEventSource(serverBaseURL, {
    signal,
    openWhenHidden: true,
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      "X-Accel-Buffering": "no",
    },
    body: msg,
    async onopen(res) {
      if (res.ok && res.status === 200) {
        return;
      }

      if (res.status >= 400 && res.status < 500 && res.status !== 429) {
        console.log("Client-side error", res);
      }
    },
    onmessage(event) {
      if (!event.data.trim()) {
        return;
      }

      try {
        onEvent(JSON.parse(event.data) as unknown);
      } catch (error) {
        console.log(error);
        console.log(`|${JSON.stringify(event.data)}| is not valid JSON`);
      }
    },
    onclose() {
      console.log("Connection closed by the server");
    },
    onerror(err) {
      console.log("There was an error from server", err);
    },
  });
}
