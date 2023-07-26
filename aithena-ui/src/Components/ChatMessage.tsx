import { fetchEventSource } from "@microsoft/fetch-event-source";

const serverBaseURL = "http://localhost:8080/v1/chat/";

type MessageHandler = (data: any) => void;

export const ChatMessage = async (onEvent: MessageHandler, message: string) => {
  console.log(`fetching ${message}`);
  let msg = JSON.stringify({ input: message });
  console.log(`input: ${msg}`);

  await fetchEventSource(`${serverBaseURL}`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ input: message }),
    async onopen(res) {
      if (res.ok && res.status === 200) {
        console.log("Connection made ", res);
      } else if (res.status >= 400 && res.status < 500 && res.status !== 429) {
        console.log("Client-side error ", res);
      }
    },
    onmessage(event) {
      // console.log(event.data);
      // const parsedData = JSON.parse(event.data);
      onEvent((data: any) => [data, event.data]); // Important to set the data this way, otherwise old data may be overwritten if the stream is too fast
    },
    onclose() {
      console.log("Connection closed by the server");
    },
    onerror(err) {
      console.log("There was an error from server", err);
    },
  });
};
