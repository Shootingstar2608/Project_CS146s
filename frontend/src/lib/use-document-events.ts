"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BackendPaper, DocumentJobEvent, documentEventsUrl } from "@/lib/api";
import { queryKeys } from "@/lib/queries";

export function useDocumentEvents(documents: BackendPaper[]) {
  const queryClient = useQueryClient();
  const socketsRef = useRef<Map<string, WebSocket>>(new Map());

  useEffect(() => {
    const sockets = socketsRef.current;
    const processingIds = new Set(
      documents.filter((doc) => doc.status === "processing").map((doc) => doc.id)
    );

    for (const id of processingIds) {
      if (sockets.has(id)) continue;
      const socket = new WebSocket(documentEventsUrl(id));
      sockets.set(id, socket);

      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as DocumentJobEvent;
        if (event.status === "heartbeat") return;

        queryClient.setQueryData<BackendPaper[]>(queryKeys.documents, (current) =>
          current?.map((paper) =>
            paper.id === event.document_id
              ? {
                  ...paper,
                  status: event.status === "failed" ? "failed" : event.status === "completed" ? "completed" : "processing",
                  errorMessage: event.status === "failed" ? event.message : paper.errorMessage,
                  entityCount: Number(event.metadata?.entity_count ?? paper.entityCount ?? 0),
                  relationCount: Number(event.metadata?.relation_count ?? paper.relationCount ?? 0),
                }
              : paper
          ) ?? current
        );

        if (event.status === "completed" || event.status === "failed") {
          queryClient.invalidateQueries({ queryKey: queryKeys.documents });
          queryClient.invalidateQueries({ queryKey: ["graph"] });
          socket.close();
          sockets.delete(event.document_id);
        }
      };

      socket.onclose = () => sockets.delete(id);
    }

    for (const [id, socket] of sockets) {
      if (!processingIds.has(id)) {
        socket.close();
        sockets.delete(id);
      }
    }
  }, [documents, queryClient]);

  useEffect(() => {
    const sockets = socketsRef.current;
    return () => {
      for (const socket of sockets.values()) socket.close();
      sockets.clear();
    };
  }, []);
}
