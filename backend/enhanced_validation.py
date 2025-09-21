from typing import List, Dict, Any, Tuple, Set, Optional
from collections import defaultdict
from models import NodeData, Edge, Node
from exceptions import (
    ValidationException, 
    InvalidNodeTypeException,
    CycleDetectedException,
    DataTypeMismatchException,
    IncompletePipelineException,
    ErrorCode
)


# Node type definitions with their characteristics
NODE_TYPE_DEFINITIONS = {
    "input": {
        "display_name": "Input",
        "inputs": [],
        "outputs": ["data"],
        "output_types": {"data": "any"},
        "required_fields": ["inputName", "inputType"],
        "description": "Provides input data to the pipeline"
    },
    "output": {
        "display_name": "Output", 
        "inputs": ["data"],
        "outputs": [],
        "input_types": {"data": "any"},
        "required_fields": ["outputName", "outputType"],
        "description": "Receives output data from the pipeline"
    },
    "text": {
        "display_name": "Text",
        "inputs": ["template_vars"],
        "outputs": ["text"],
        "input_types": {"template_vars": "any"},
        "output_types": {"text": "string"},
        "required_fields": ["text"],
        "description": "Processes text with variable substitution"
    },
    "llm": {
        "display_name": "LLM",
        "inputs": ["prompt", "system", "context"],
        "outputs": ["response"],
        "input_types": {"prompt": "string", "system": "string", "context": "string"},
        "output_types": {"response": "string"},
        "required_fields": [],
        "description": "Large Language Model processing"
    },
    "filter": {
        "display_name": "Filter",
        "inputs": ["data"],
        "outputs": ["filtered_data"],
        "input_types": {"data": "array"},
        "output_types": {"filtered_data": "array"},
        "required_fields": ["condition"],
        "description": "Filters data based on conditions"
    },
    "aggregate": {
        "display_name": "Aggregate",
        "inputs": ["data"],
        "outputs": ["aggregated"],
        "input_types": {"data": "array"},
        "output_types": {"aggregated": "object"},
        "required_fields": ["operation"],
        "description": "Aggregates data using specified operations"
    },
    "transform": {
        "display_name": "Transform",
        "inputs": ["data"],
        "outputs": ["transformed"],
        "input_types": {"data": "any"},
        "output_types": {"transformed": "any"},
        "required_fields": ["transformation"],
        "description": "Transforms data using specified rules"
    },
    "http": {
        "display_name": "HTTP Request",
        "inputs": ["url", "headers", "body"],
        "outputs": ["response"],
        "input_types": {"url": "string", "headers": "object", "body": "any"},
        "output_types": {"response": "object"},
        "required_fields": ["method", "url"],
        "description": "Makes HTTP requests"
    },
    "debug": {
        "display_name": "Debug",
        "inputs": ["data"],
        "outputs": ["data"],
        "input_types": {"data": "any"},
        "output_types": {"data": "any"},
        "required_fields": [],
        "description": "Debug and inspect data flow"
    }
}


class EnhancedValidator:
    """Enhanced validation system with semantic and type checking"""
    
    def __init__(self):
        self.valid_node_types = set(NODE_TYPE_DEFINITIONS.keys())
    
    def validate_pipeline_comprehensive(
        self, 
        nodes: List[Node], 
        edges: List[Edge]
    ) -> Tuple[bool, bool, List[str], List[str]]:
        """
        Comprehensive pipeline validation
        Returns: (is_dag, is_pipeline, dag_messages, pipeline_messages)
        """
        try:
            # Step 1: Basic structure validation
            self._validate_basic_structure(nodes, edges)
            
            # Step 2: Node type and configuration validation
            self._validate_node_types_and_configs(nodes)
            
            # Step 3: Edge connection validation
            self._validate_edge_connections(nodes, edges)
            
            # Step 4: DAG validation (existing logic enhanced)
            graph, in_degree, node_ids = self._build_graph(nodes, edges)
            is_dag, dag_messages = self._validate_dag_enhanced(graph, in_degree, node_ids, edges)
            
            # Step 5: Data type compatibility validation
            if is_dag:
                self._validate_data_types(nodes, edges)
            
            # Step 6: Pipeline completeness validation
            pipeline_messages = []
            is_pipeline = True
            
            if is_dag:
                is_pipeline, pipeline_messages = self._validate_pipeline_completeness(nodes, edges)
            
            return is_dag, is_pipeline, dag_messages, pipeline_messages
            
        except ValidationException as e:
            # Convert validation exceptions to message format
            if e.error_code == ErrorCode.CYCLE_DETECTED:
                return False, False, [e.message], []
            else:
                return True, False, [], [e.message]
    
    def _validate_basic_structure(self, nodes: List[Node], edges: List[Edge]) -> None:
        """Validate basic structure requirements"""
        if not isinstance(nodes, list):
            raise ValidationException("Nodes must be a list", ErrorCode.INVALID_INPUT_FORMAT)
        
        if not isinstance(edges, list):
            raise ValidationException("Edges must be a list", ErrorCode.INVALID_INPUT_FORMAT)
        
        # Check for duplicate node IDs
        node_ids = [node.id for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            duplicates = [nid for nid in set(node_ids) if node_ids.count(nid) > 1]
            raise ValidationException(
                f"Duplicate node IDs found: {duplicates}",
                ErrorCode.VALIDATION_FAILED,
                suggestion="Ensure all node IDs are unique"
            )
    
    def _validate_node_types_and_configs(self, nodes: List[Node]) -> None:
        """Validate node types and their configurations"""
        for node in nodes:
            # Validate node type
            node_type = node.data.nodeType
            if node_type not in self.valid_node_types:
                raise InvalidNodeTypeException(node_type, list(self.valid_node_types))
            
            # Validate node configuration
            self._validate_node_configuration(node)
    
    def _validate_node_configuration(self, node: Node) -> None:
        """Validate individual node configuration"""
        node_type = node.data.nodeType
        node_def = NODE_TYPE_DEFINITIONS[node_type]
        
        # Check required fields (if node has data beyond nodeType)
        node_data = node.data.dict() if hasattr(node.data, 'dict') else {}
        
        for required_field in node_def.get("required_fields", []):
            if required_field not in node_data or not node_data[required_field]:
                raise ValidationException(
                    f"Node '{node.id}' of type '{node_type}' is missing required field: {required_field}",
                    ErrorCode.MISSING_REQUIRED_FIELD,
                    field=required_field,
                    suggestion=f"Add the '{required_field}' field to node '{node.id}'"
                )
    
    def _validate_edge_connections(self, nodes: List[Node], edges: List[Edge]) -> None:
        """Validate edge connections between nodes"""
        node_map = {node.id: node for node in nodes}
        
        for edge in edges:
            # Check if source and target nodes exist
            if edge.source not in node_map:
                raise ValidationException(
                    f"Edge references non-existent source node: {edge.source}",
                    ErrorCode.INVALID_EDGE_CONNECTION,
                    suggestion="Ensure all edges reference valid node IDs"
                )
            
            if edge.target not in node_map:
                raise ValidationException(
                    f"Edge references non-existent target node: {edge.target}",
                    ErrorCode.INVALID_EDGE_CONNECTION,
                    suggestion="Ensure all edges reference valid node IDs"
                )
            
            # Validate connection compatibility
            source_node = node_map[edge.source]
            target_node = node_map[edge.target]
            
            self._validate_connection_compatibility(source_node, target_node, edge)
    
    def _validate_connection_compatibility(self, source_node: Node, target_node: Node, edge: Edge) -> None:
        """Validate that two nodes can be connected"""
        source_type = source_node.data.nodeType
        target_type = target_node.data.nodeType
        
        source_def = NODE_TYPE_DEFINITIONS[source_type]
        target_def = NODE_TYPE_DEFINITIONS[target_type]
        
        # Check if source node can have outputs
        if not source_def.get("outputs"):
            raise ValidationException(
                f"Node '{source_node.id}' of type '{source_type}' cannot have output connections",
                ErrorCode.INVALID_EDGE_CONNECTION,
                suggestion=f"Connect from a node that produces outputs"
            )
        
        # Check if target node can have inputs
        if not target_def.get("inputs"):
            raise ValidationException(
                f"Node '{target_node.id}' of type '{target_type}' cannot have input connections",
                ErrorCode.INVALID_EDGE_CONNECTION,
                suggestion=f"Connect to a node that accepts inputs"
            )
    
    def _validate_data_types(self, nodes: List[Node], edges: List[Edge]) -> None:
        """Validate data type compatibility between connected nodes"""
        node_map = {node.id: node for node in nodes}
        
        for edge in edges:
            source_node = node_map[edge.source]
            target_node = node_map[edge.target]
            
            source_type = source_node.data.nodeType
            target_type = target_node.data.nodeType
            
            source_def = NODE_TYPE_DEFINITIONS[source_type]
            target_def = NODE_TYPE_DEFINITIONS[target_type]
            
            # Get output types from source and input types from target
            source_output_types = source_def.get("output_types", {})
            target_input_types = target_def.get("input_types", {})
            
            # For now, we'll do basic type checking
            # In a real system, this would be more sophisticated with handle-specific validation
            if source_output_types and target_input_types:
                # Check if there's any compatible type (simplified check)
                source_types = set(source_output_types.values())
                target_types = set(target_input_types.values())
                
                # Allow 'any' type to be compatible with everything
                if "any" not in source_types and "any" not in target_types:
                    if not source_types.intersection(target_types):
                        # Get the primary types for error message
                        primary_source_type = next(iter(source_types), "unknown")
                        primary_target_type = next(iter(target_types), "unknown")
                        
                        raise DataTypeMismatchException(
                            source_node.id, target_node.id, 
                            primary_source_type, primary_target_type
                        )
    
    def _validate_pipeline_completeness(self, nodes: List[Node], edges: List[Edge]) -> Tuple[bool, List[str]]:
        """Validate that the pipeline is complete (all required inputs connected)"""
        node_map = {node.id: node for node in nodes}
        edge_targets = defaultdict(list)
        
        # Build map of what's connected to each node
        for edge in edges:
            edge_targets[edge.target].append(edge.source)
        
        missing_connections = []
        pipeline_messages = []
        
        for node in nodes:
            node_type = node.data.nodeType
            node_def = NODE_TYPE_DEFINITIONS[node_type]
            required_inputs = node_def.get("inputs", [])
            
            # Check if node has required inputs but no connections
            if required_inputs and node.id not in edge_targets:
                missing_connections.append({
                    "node_id": node.id,
                    "node_type": node_type,
                    "required_inputs": required_inputs
                })
        
        if missing_connections:
            pipeline_messages.append(
                f"Pipeline has {len(missing_connections)} node(s) with unconnected required inputs"
            )
            return False, pipeline_messages
        
        return True, pipeline_messages
    
    def _build_graph(self, nodes: List[Node], edges: List[Edge]) -> Tuple[Dict[str, List[str]], Dict[str, int], Set[str]]:
        """Build adjacency graph and track in-degrees"""
        graph: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = defaultdict(int)
        node_ids = {node.id for node in nodes}

        for edge in edges:
            graph[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        return graph, in_degree, node_ids
    
    def _validate_dag_enhanced(
        self, 
        graph: Dict[str, List[str]], 
        in_degree: Dict[str, int], 
        node_ids: Set[str], 
        edges: List[Edge]
    ) -> Tuple[bool, List[str]]:
        """Enhanced DAG validation with better error messages"""
        dag_messages = []
        
        # Empty graph validation
        if not node_ids:
            return True, dag_messages
        
        # Check for self-loops in edges
        self_loops = [edge for edge in edges if edge.source == edge.target]
        if self_loops:
            affected_nodes = [edge.source for edge in self_loops]
            raise CycleDetectedException("Self-loop detected (node connected to itself)", affected_nodes)

        # Kahn's algorithm for cycle detection
        zero_in_degree = [node for node in node_ids if in_degree[node] == 0]
        visited_count = 0
        temp_in_degree = in_degree.copy()
        visited_nodes = set()

        while zero_in_degree:
            current = zero_in_degree.pop(0)
            visited_nodes.add(current)
            visited_count += 1

            for neighbor in graph[current]:
                temp_in_degree[neighbor] -= 1
                if temp_in_degree[neighbor] == 0:
                    zero_in_degree.append(neighbor)

        if visited_count != len(node_ids):
            # Find the cycle
            remaining = node_ids - visited_nodes
            if len(remaining) == 2:
                cycle_description = "Direct cycle detected (A → B → A)"
            else:
                cycle_description = f"Complex cycle detected involving {len(remaining)} nodes"
            
            raise CycleDetectedException(cycle_description, list(remaining))

        return True, dag_messages


# Global validator instance
enhanced_validator = EnhancedValidator()


# Updated validation function that maintains backward compatibility
def validate_graph(nodes: List[NodeData], edges: List[Edge]) -> Tuple[bool, bool, List[str], List[str]]:
    """
    Enhanced validation function with backward compatibility
    Converts NodeData to Node format for enhanced validation
    """
    try:
        # Convert NodeData to Node format for enhanced validation
        enhanced_nodes = []
        for i, node_data in enumerate(nodes):
            enhanced_node = Node(
                id=node_data.id,
                type=node_data.nodeType,
                position={"x": 0, "y": 0},  # Default position
                data=node_data,
                width=200,  # Default width
                height=100  # Default height
            )
            enhanced_nodes.append(enhanced_node)
        
        return enhanced_validator.validate_pipeline_comprehensive(enhanced_nodes, edges)
        
    except ValidationException as e:
        # Handle validation exceptions gracefully
        if e.error_code == ErrorCode.CYCLE_DETECTED:
            return False, False, [e.message], []
        else:
            return True, False, [], [e.message]
    except Exception as e:
        # Fallback for unexpected errors
        return True, False, [], [f"Validation error: {str(e)}"]
