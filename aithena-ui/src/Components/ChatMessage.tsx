import { fetchEventSource } from "@microsoft/fetch-event-source";

const serverBaseURL = `${import.meta.env.VITE_API_URL}/v1/question/`;
console.log(`serverBaseURL: ${serverBaseURL}`);

type MessageHandler = (data: any) => void;

export const ChatMessage = async (onEvent: MessageHandler, message: string) => {
  console.log(`fetching ${message}`);
  let msg = JSON.stringify({ input: message, stream: true, limit: 8 });
  console.log(`input: ${msg}`);

  await fetchEventSource(`${serverBaseURL}`, {
    openWhenHidden: true, // https://github.com/Azure/fetch-event-source/issues/17
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
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
