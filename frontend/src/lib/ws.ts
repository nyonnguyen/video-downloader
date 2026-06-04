import { useEffect } from "react";
import { useTasksStore } from "@/store/tasks";
import { useLibraryStore } from "@/store/library";
import type { WSEvent } from "./types";

let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws/tasks`);

  socket.onopen = () => console.log("[ws] connected");
  socket.onmessage = (e) => {
    try {
      const evt: WSEvent = JSON.parse(e.data);
      useTasksStore.getState().applyEvent(evt);
      if (evt.type === "done") {
        useLibraryStore.getState().fetch();
      }
    } catch (err) {
      console.error("[ws] bad message", err);
    }
  };
  socket.onclose = () => {
    console.log("[ws] closed, reconnecting in 2s");
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connect, 2000);
  };
  socket.onerror = () => socket?.close();
}

export function useWebSocketBootstrap() {
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
      socket = null;
    };
  }, []);
}
