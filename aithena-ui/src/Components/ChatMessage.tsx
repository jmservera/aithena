import { fetchEventSource } from "@microsoft/fetch-event-source";

const serverBaseURL = `${import.meta.env.VITE_API_URL}/v1/question/`;
console.log(`serverBaseURL: ${serverBaseURL}`);

type MessageHandler = (data: any) => void;

export type CreateCompletionRequest = {
  suffix?: string | null;
  max_tokens?: number; // default 16
  temperature?: number; // max 2, min 0, default 0.8
  top_p?: number; // max 1, min 0, default 0.95
  mirostat_mode?: number; // max 2, min 0, default 0
  mirostat_tau?: number; // max 10, min 0, default 5
  mirostat_eta?: number; // max 1, min 0.001, default 0.1
  echo?: boolean;
  stream?: boolean;
  logprobs?: number;
  presence_penalty?: number; // max 2, min -2, default 0
  frequency_penalty?: number; // max 2, min -2, default 0
  n?: number; // default 1
  best_of?: number;
  top_k?: number; // min 0, max 40, default 40
  repeat_penalty?: number; // min 0, default 1.1
};

export type ChatMessageProps = {
  message: string;
  limit?: number;
  model_properties: CreateCompletionRequest;
};

export const ChatMessage = async (
  onEvent: MessageHandler,
  messageProps: ChatMessageProps
) => {
  const { message, limit = 12, model_properties } = messageProps;
  model_properties.stream = true;
  console.log(`message limit: ${limit}`);

  console.log(`fetching ${message}`);
  let msg = JSON.stringify({
    input: message,
    limit: limit,
    model_properties: model_properties,
  });
  console.log(`input: ${msg}`);

  await fetchEventSource(`${serverBaseURL}`, {
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
