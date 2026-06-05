"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BackendPaper,
  deleteDocument,
  getDocuments,
  getGraphData,
  getGraphSubgraph,
} from "./api";

export const queryKeys = {
  documents: ["documents"] as const,
  graph: (view: string) => ["graph", view] as const,
};

/** All uploaded papers (Postgres rows joined with Neo4j metadata). */
export function useDocuments() {
  return useQuery<BackendPaper[]>({
    queryKey: queryKeys.documents,
    queryFn: getDocuments,
  });
}

/**
 * Knowledge graph for the current view. `view` is either "global" or a
 * paper id; the query key switches automatically so each view is cached.
 */
export function useGraph(view: string) {
  return useQuery({
    queryKey: queryKeys.graph(view),
    queryFn: () => (view === "global" ? getGraphData() : getGraphSubgraph(view)),
  });
}

/** Delete a document everywhere (Postgres + Neo4j + FAISS + disk). */
export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    // Optimistically drop the row so the UI feels instant, roll back on error.
    onMutate: async (id: string) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.documents });
      const previous = queryClient.getQueryData<BackendPaper[]>(queryKeys.documents);
      queryClient.setQueryData<BackendPaper[]>(
        queryKeys.documents,
        (old) => old?.filter((paper) => paper.id !== id) ?? []
      );
      return { previous };
    },
    onError: (_err, _id, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.documents, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.documents });
      queryClient.invalidateQueries({ queryKey: ["graph"] });
    },
  });
}
