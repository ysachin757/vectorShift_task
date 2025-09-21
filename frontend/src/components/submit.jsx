import { toast } from "sonner";
import { Play } from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";
import { useStore } from "./store";
import { validatePipeline } from "../services/api";

export const SubmitButton = ({ className }) => {
  const [isLoading, setIsLoading] = useState(false);
  const nodes = useStore((state) => state.getNodes());
  const edges = useStore((state) => state.getEdges());
  const setPipelineStats = useStore((state) => state.setPipelineStats);
  const setStatsDialogOpen = useStore((state) => state.setStatsDialogOpen);

  const handleSubmit = async () => {
    const store = useStore.getState();
    store.setLoading(true, 'validatePipeline');
    
    try {
      const response = await validatePipeline(nodes, edges);
      
      setPipelineStats(response);
      setStatsDialogOpen(true);
      
      toast.success("Pipeline Validation Successful", {
        description: `Analyzed ${response.num_nodes} nodes and ${response.num_edges} edges`,
        duration: 3000,
      });
      
      store.clearError();
    } catch (error) {
      console.error("Pipeline validation failed:", error);
      
      // The API service already shows user-friendly error toasts
      // Just set the error in the store for other components to react to
      store.setError(error, 'validatePipeline');
      setPipelineStats(null);
    } finally {
      store.setLoading(false);
      setIsLoading(false);
    }
  };

  return (
    <Button
      className={cn("text-sm h-16 w-16 bg-indigo-800", className)}
      onClick={handleSubmit}
      disabled={isLoading}
    >
      <Play />
    </Button>
  );
};
