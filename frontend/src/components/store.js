import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
} from "reactflow";

const DEFAULT_MARKER = {
  type: MarkerType.ArrowClosed,
  width: 12,
  height: 12,
  color: "#b1b1b7",
};

export const useStore = create(
  persist(
    (set, get) => ({
      // State
      nodes: [],
      edges: [],
      nodeIDs: {},
      pipelineStats: null,
      isStatsDialogOpen: false,
      validationMessages: [],
      showConfetti: false,
      isCustomEdge: true,
      isAnimated: true,
      isMenuOpen: false,
      
      // Loading and error states
      isLoading: false,
      error: null,
      lastAction: null,
      retryCount: 0,

      // Getters
      getNodes: () => get().nodes,
      getEdges: () => get().edges,
      getNodeID: (type) => {
        const newIDs = { ...get().nodeIDs };
        if (newIDs[type] === undefined) {
          newIDs[type] = 0;
        }
        newIDs[type] += 1;
        set({ nodeIDs: newIDs });
        return `${type}-${newIDs[type]}`;
      },

      // Error handling
      setError: (error, action = null) => {
        console.error(`Store error during ${action}:`, error);
        set({ 
          error, 
          lastAction: action,
          isLoading: false 
        });
      },
      clearError: () => set({ error: null, lastAction: null, retryCount: 0 }),
      setLoading: (isLoading, action = null) => set({ 
        isLoading, 
        lastAction: action,
        error: isLoading ? null : get().error 
      }),

      // Node operations
      addNode: (node) => {
        try {
          set({
            nodes: [...get().nodes, node],
          });
          get().clearError();
        } catch (error) {
          get().setError(error, 'addNode');
        }
      },
      onNodesChange: (changes) => {
        try {
          set({
            nodes: applyNodeChanges(changes, get().nodes),
          });
        } catch (error) {
          get().setError(error, 'onNodesChange');
        }
      },
      updateNodeField: (nodeId, fieldName, fieldValue) => {
        try {
          set({
            nodes: get().nodes.map((node) => {
              if (node.id === nodeId) {
                node.data = { ...node.data, [fieldName]: fieldValue };
              }
              return node;
            }),
          });
          get().clearError();
        } catch (error) {
          get().setError(error, 'updateNodeField');
        }
      },
      removeNode: (nodeId) => {
        try {
          set({
            nodes: get().nodes.filter((node) => node.id !== nodeId),
            edges: get().edges.filter(
              (edge) => edge.source !== nodeId && edge.target !== nodeId,
            ),
          });
          get().clearError();
        } catch (error) {
          get().setError(error, 'removeNode');
        }
      },

      // Edge operations
      onEdgesChange: (changes) => {
        try {
          set({
            edges: applyEdgeChanges(changes, get().edges),
          });
        } catch (error) {
          get().setError(error, 'onEdgesChange');
        }
      },
      setEdges: (updater) => {
        set({
          edges: typeof updater === "function" ? updater(get().edges) : updater,
        });
      },
      onConnect: (connection) => {
        set({
          edges: addEdge(
            {
              ...connection,
              type: get().isCustomEdge ? "custom" : "base",
              animated: get().isAnimated,
              markerEnd: DEFAULT_MARKER,
            },
            get().edges,
          ),
        });
      },
      setPipelineStats: (stats) =>
        set({
          pipelineStats: stats,
          showConfetti: stats?.is_dag && stats?.is_pipeline,
        }),
      setStatsDialogOpen: (isOpen) =>
        set((state) => ({
          isStatsDialogOpen: isOpen,
          pipelineStats: isOpen ? state.pipelineStats : null,
          showConfetti: isOpen ? state.showConfetti : false,
        })),
      toggleEdgeType: () =>
        set((state) => {
          const newIsCustomEdge = !state.isCustomEdge;
          return {
            isCustomEdge: newIsCustomEdge,
            edges: state.edges.map((edge) => ({
              ...edge,
              type: newIsCustomEdge ? "custom" : "base",
              deletable: newIsCustomEdge,
            })),
          };
        }),

      toggleAnimation: () =>
        set((state) => {
          const newIsAnimated = !state.isAnimated;
          return {
            isAnimated: newIsAnimated,
            edges: state.edges.map((edge) => ({
              ...edge,
              animated: newIsAnimated,
            })),
          };
        }),
      toggleMenu: () => set((state) => ({ isMenuOpen: !state.isMenuOpen })),
    }),
    {
      name: "pipeline-storage",
      partialize: (state) => ({
        nodes: state.nodes,
        edges: state.edges,
        nodeIDs: state.nodeIDs,
        isCustomEdge: state.isCustomEdge,
        isAnimated: state.isAnimated,
      }),
    },
  ),
);
