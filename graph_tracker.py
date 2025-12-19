"""
Graph-Based Hierarchical Tracking Module
Uses hierarchical graph structures with jersey numbers, team IDs, and positions as nodes
for better long-term player tracking consistency.

Based on state-of-the-art graph-based tracking methods for sports analytics.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GraphNode:
    """Node in the tracking graph"""
    node_id: str  # Unique node identifier
    node_type: str  # 'player', 'jersey', 'team', 'position_zone'
    track_id: Optional[int] = None  # Associated track ID (if player node)
    player_id: Optional[str] = None  # Associated player ID (if known)
    jersey_number: Optional[str] = None  # Jersey number (if jersey node)
    team: Optional[str] = None  # Team name (if team node)
    position_zone: Optional[Tuple[int, int]] = None  # (x_zone, y_zone) if position node
    features: Optional[np.ndarray] = None  # Feature vector
    confidence: float = 0.5  # Confidence score
    frame_num: int = 0  # Last seen frame
    created_at: str = ""  # Creation timestamp


@dataclass
class GraphEdge:
    """Edge in the tracking graph"""
    source_id: str  # Source node ID
    target_id: str  # Target node ID
    edge_type: str  # 'has_jersey', 'on_team', 'in_zone', 'similar_to'
    weight: float = 1.0  # Edge weight (similarity, confidence, etc.)
    frame_num: int = 0  # Frame when edge was created/updated
    created_at: str = ""  # Creation timestamp


class GraphTracker:
    """
    Hierarchical graph-based tracker for long-term player tracking.
    
    Graph Structure:
    - Player nodes: Individual player identities
    - Jersey nodes: Jersey numbers (shared by players)
    - Team nodes: Team identities
    - Position zone nodes: Field zones (10x10 grid)
    
    Edges:
    - Player -> Jersey: "has_jersey" (player wears jersey number)
    - Player -> Team: "on_team" (player is on team)
    - Player -> Position: "in_zone" (player is in zone)
    - Player -> Player: "similar_to" (similar appearance/features)
    """
    
    def __init__(self,
                 position_grid_size: Tuple[int, int] = (10, 10),  # Field divided into 10x10 grid
                 max_nodes_per_type: int = 1000,  # Maximum nodes per type
                 edge_decay_rate: float = 0.95,  # Edge weight decay per frame
                 min_edge_weight: float = 0.1):  # Minimum edge weight to keep
        """
        Initialize Graph Tracker
        
        Args:
            position_grid_size: Size of position grid (x, y)
            max_nodes_per_type: Maximum nodes per type
            edge_decay_rate: Edge weight decay rate (0-1)
            min_edge_weight: Minimum edge weight to keep edge
        """
        self.position_grid_size = position_grid_size
        self.max_nodes_per_type = max_nodes_per_type
        self.edge_decay_rate = edge_decay_rate
        self.min_edge_weight = min_edge_weight
        
        # Graph structure
        self.nodes: Dict[str, GraphNode] = {}  # node_id -> GraphNode
        self.edges: Dict[str, List[GraphEdge]] = defaultdict(list)  # source_id -> [GraphEdge]
        self.reverse_edges: Dict[str, List[GraphEdge]] = defaultdict(list)  # target_id -> [GraphEdge]
        
        # Indexes for fast lookup
        self.track_to_node: Dict[int, str] = {}  # track_id -> node_id
        self.player_to_node: Dict[str, str] = {}  # player_id -> node_id
        self.jersey_to_nodes: Dict[str, List[str]] = defaultdict(list)  # jersey_number -> [node_ids]
        self.team_to_nodes: Dict[str, List[str]] = defaultdict(list)  # team -> [node_ids]
        self.zone_to_nodes: Dict[Tuple[int, int], List[str]] = defaultdict(list)  # zone -> [node_ids]
        
        # Statistics
        self.stats = {
            'nodes_created': 0,
            'edges_created': 0,
            'matches_found': 0,
            'matches_improved': 0
        }
    
    def _get_position_zone(self, x: float, y: float, field_width: float, field_height: float) -> Tuple[int, int]:
        """Convert position to zone coordinates"""
        norm_x = max(0.0, min(1.0, x / (field_width + 1e-8)))
        norm_y = max(0.0, min(1.0, y / (field_height + 1e-8)))
        
        zone_x = int(norm_x * self.position_grid_size[0])
        zone_y = int(norm_y * self.position_grid_size[1])
        
        zone_x = max(0, min(self.position_grid_size[0] - 1, zone_x))
        zone_y = max(0, min(self.position_grid_size[1] - 1, zone_y))
        
        return (zone_x, zone_y)
    
    def create_or_update_player_node(self,
                                    track_id: int,
                                    features: Optional[np.ndarray] = None,
                                    player_id: Optional[str] = None,
                                    jersey_number: Optional[str] = None,
                                    team: Optional[str] = None,
                                    position: Optional[Tuple[float, float]] = None,
                                    field_size: Optional[Tuple[float, float]] = None,
                                    confidence: float = 0.5,
                                    frame_num: int = 0) -> str:
        """
        Create or update a player node in the graph
        
        Args:
            track_id: Track identifier
            features: Feature vector
            player_id: Known player ID (if available)
            jersey_number: Jersey number
            team: Team name
            position: (x, y) position
            field_size: (width, height) of field
            confidence: Confidence score
            frame_num: Current frame number
            
        Returns:
            Node ID
        """
        # Check if node already exists for this track
        if track_id in self.track_to_node:
            node_id = self.track_to_node[track_id]
            node = self.nodes[node_id]
            
            # Update node
            if features is not None:
                node.features = features.copy()
            if player_id is not None:
                node.player_id = player_id
            if jersey_number is not None:
                node.jersey_number = jersey_number
            if team is not None:
                node.team = team
            node.confidence = confidence
            node.frame_num = frame_num
            
            # Update edges
            self._update_player_edges(node_id, jersey_number, team, position, field_size, frame_num)
            
            return node_id
        
        # Create new node
        node_id = f"player_{track_id}_{frame_num}"
        node = GraphNode(
            node_id=node_id,
            node_type='player',
            track_id=track_id,
            player_id=player_id,
            jersey_number=jersey_number,
            team=team,
            features=features.copy() if features is not None else None,
            confidence=confidence,
            frame_num=frame_num,
            created_at=datetime.now().isoformat()
        )
        
        self.nodes[node_id] = node
        self.track_to_node[track_id] = node_id
        
        if player_id:
            self.player_to_node[player_id] = node_id
        
        self.stats['nodes_created'] += 1
        
        # Create edges
        self._update_player_edges(node_id, jersey_number, team, position, field_size, frame_num)
        
        return node_id
    
    def _update_player_edges(self,
                            node_id: str,
                            jersey_number: Optional[str],
                            team: Optional[str],
                            position: Optional[Tuple[float, float]],
                            field_size: Optional[Tuple[float, float]],
                            frame_num: int):
        """Update edges for a player node"""
        node = self.nodes[node_id]
        
        # Edge to jersey node
        if jersey_number:
            jersey_node_id = self._get_or_create_jersey_node(jersey_number, frame_num)
            self._add_or_update_edge(node_id, jersey_node_id, 'has_jersey', 1.0, frame_num)
        
        # Edge to team node
        if team:
            team_node_id = self._get_or_create_team_node(team, frame_num)
            self._add_or_update_edge(node_id, team_node_id, 'on_team', 1.0, frame_num)
        
        # Edge to position zone node
        if position and field_size:
            zone = self._get_position_zone(position[0], position[1], field_size[0], field_size[1])
            zone_node_id = self._get_or_create_zone_node(zone, frame_num)
            self._add_or_update_edge(node_id, zone_node_id, 'in_zone', 1.0, frame_num)
    
    def _get_or_create_jersey_node(self, jersey_number: str, frame_num: int) -> str:
        """Get or create a jersey number node"""
        node_id = f"jersey_{jersey_number}"
        
        if node_id not in self.nodes:
            node = GraphNode(
                node_id=node_id,
                node_type='jersey',
                jersey_number=jersey_number,
                frame_num=frame_num,
                created_at=datetime.now().isoformat()
            )
            self.nodes[node_id] = node
            self.jersey_to_nodes[jersey_number].append(node_id)
            self.stats['nodes_created'] += 1
        
        return node_id
    
    def _get_or_create_team_node(self, team: str, frame_num: int) -> str:
        """Get or create a team node"""
        node_id = f"team_{team}"
        
        if node_id not in self.nodes:
            node = GraphNode(
                node_id=node_id,
                node_type='team',
                team=team,
                frame_num=frame_num,
                created_at=datetime.now().isoformat()
            )
            self.nodes[node_id] = node
            self.team_to_nodes[team].append(node_id)
            self.stats['nodes_created'] += 1
        
        return node_id
    
    def _get_or_create_zone_node(self, zone: Tuple[int, int], frame_num: int) -> str:
        """Get or create a position zone node"""
        node_id = f"zone_{zone[0]}_{zone[1]}"
        
        if node_id not in self.nodes:
            node = GraphNode(
                node_id=node_id,
                node_type='position_zone',
                position_zone=zone,
                frame_num=frame_num,
                created_at=datetime.now().isoformat()
            )
            self.nodes[node_id] = node
            self.zone_to_nodes[zone].append(node_id)
            self.stats['nodes_created'] += 1
        
        return node_id
    
    def _add_or_update_edge(self,
                           source_id: str,
                           target_id: str,
                           edge_type: str,
                           weight: float,
                           frame_num: int):
        """Add or update an edge"""
        # Check if edge exists
        for edge in self.edges[source_id]:
            if edge.target_id == target_id and edge.edge_type == edge_type:
                # Update existing edge
                edge.weight = max(edge.weight, weight)  # Keep maximum weight
                edge.frame_num = frame_num
                return
        
        # Create new edge
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            frame_num=frame_num,
            created_at=datetime.now().isoformat()
        )
        
        self.edges[source_id].append(edge)
        self.reverse_edges[target_id].append(edge)
        self.stats['edges_created'] += 1
    
    def find_matching_players(self,
                             features: np.ndarray,
                             jersey_number: Optional[str] = None,
                             team: Optional[str] = None,
                             position: Optional[Tuple[float, float]] = None,
                             field_size: Optional[Tuple[float, float]] = None,
                             similarity_threshold: float = 0.5) -> List[Tuple[str, float]]:
        """
        Find matching players using graph structure
        
        Args:
            features: Feature vector to match
            jersey_number: Optional jersey number constraint
            team: Optional team constraint
            position: Optional position constraint
            field_size: Field size for position zone calculation
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            List of (node_id, similarity_score) tuples, sorted by similarity
        """
        candidates = []
        
        # Filter by constraints
        candidate_nodes = []
        
        if jersey_number:
            # Get nodes with this jersey number
            jersey_node_ids = self.jersey_to_nodes.get(jersey_number, [])
            for jersey_node_id in jersey_node_ids:
                # Get players connected to this jersey
                for edge in self.reverse_edges[jersey_node_id]:
                    if edge.edge_type == 'has_jersey':
                        candidate_nodes.append(edge.source_id)
        
        if team:
            # Get nodes on this team
            team_node_ids = self.team_to_nodes.get(team, [])
            for team_node_id in team_node_ids:
                # Get players connected to this team
                for edge in self.reverse_edges[team_node_id]:
                    if edge.edge_type == 'on_team':
                        if edge.source_id not in candidate_nodes:
                            candidate_nodes.append(edge.source_id)
        
        if position and field_size:
            # Get nodes in this position zone
            zone = self._get_position_zone(position[0], position[1], field_size[0], field_size[1])
            zone_node_ids = self.zone_to_nodes.get(zone, [])
            for zone_node_id in zone_node_ids:
                # Get players in this zone
                for edge in self.reverse_edges[zone_node_id]:
                    if edge.edge_type == 'in_zone':
                        if edge.source_id not in candidate_nodes:
                            candidate_nodes.append(edge.source_id)
        
        # If no constraints, use all player nodes
        if not candidate_nodes:
            candidate_nodes = [node_id for node_id, node in self.nodes.items() 
                             if node.node_type == 'player' and node.features is not None]
        
        # Compute similarity to each candidate
        features_norm = features / (np.linalg.norm(features) + 1e-8)
        
        for node_id in candidate_nodes:
            node = self.nodes[node_id]
            if node.features is None:
                continue
            
            # Cosine similarity
            node_features_norm = node.features / (np.linalg.norm(node.features) + 1e-8)
            similarity = np.dot(features_norm, node_features_norm)
            
            # Boost similarity based on graph structure
            # If jersey/team/position match, boost similarity
            boost = 0.0
            if jersey_number and node.jersey_number == jersey_number:
                boost += 0.1
            if team and node.team == team:
                boost += 0.1
            if position and field_size:
                node_zone = self._get_position_zone(
                    position[0], position[1], field_size[0], field_size[1]
                )
                if node.position_zone == node_zone:
                    boost += 0.05
            
            similarity = min(1.0, similarity + boost)
            
            if similarity >= similarity_threshold:
                candidates.append((node_id, similarity))
        
        # Sort by similarity (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates
    
    def decay_edges(self, current_frame: int):
        """Decay edge weights over time"""
        edges_to_remove = []
        
        for source_id, edge_list in self.edges.items():
            for edge in edge_list:
                # Decay weight
                frames_since_update = current_frame - edge.frame_num
                if frames_since_update > 0:
                    edge.weight *= (self.edge_decay_rate ** frames_since_update)
                
                # Remove if weight too low
                if edge.weight < self.min_edge_weight:
                    edges_to_remove.append((source_id, edge))
        
        # Remove low-weight edges
        for source_id, edge in edges_to_remove:
            self.edges[source_id].remove(edge)
            if edge in self.reverse_edges[edge.target_id]:
                self.reverse_edges[edge.target_id].remove(edge)
    
    def clear_old_nodes(self, current_frame: int, max_age_frames: int = 300):
        """Remove nodes that haven't been seen recently"""
        nodes_to_remove = []
        
        for node_id, node in self.nodes.items():
            if node.node_type == 'player':
                age = current_frame - node.frame_num
                if age > max_age_frames:
                    nodes_to_remove.append(node_id)
        
        for node_id in nodes_to_remove:
            self._remove_node(node_id)
    
    def _remove_node(self, node_id: str):
        """Remove a node and all its edges"""
        if node_id not in self.nodes:
            return
        
        node = self.nodes[node_id]
        
        # Remove from indexes
        if node.track_id is not None:
            if node.track_id in self.track_to_node:
                del self.track_to_node[node.track_id]
        
        if node.player_id is not None:
            if node.player_id in self.player_to_node:
                del self.player_to_node[node.player_id]
        
        if node.jersey_number is not None:
            if node_id in self.jersey_to_nodes[node.jersey_number]:
                self.jersey_to_nodes[node.jersey_number].remove(node_id)
        
        if node.team is not None:
            if node_id in self.team_to_nodes[node.team]:
                self.team_to_nodes[node.team].remove(node_id)
        
        if node.position_zone is not None:
            if node_id in self.zone_to_nodes[node.position_zone]:
                self.zone_to_nodes[node.position_zone].remove(node_id)
        
        # Remove edges
        if node_id in self.edges:
            del self.edges[node_id]
        
        if node_id in self.reverse_edges:
            del self.reverse_edges[node_id]
        
        # Remove node
        del self.nodes[node_id]
    
    def get_stats(self) -> Dict:
        """Get tracker statistics"""
        return {
            **self.stats,
            'total_nodes': len(self.nodes),
            'total_edges': sum(len(edges) for edges in self.edges.values()),
            'player_nodes': sum(1 for n in self.nodes.values() if n.node_type == 'player'),
            'jersey_nodes': sum(1 for n in self.nodes.values() if n.node_type == 'jersey'),
            'team_nodes': sum(1 for n in self.nodes.values() if n.node_type == 'team'),
            'zone_nodes': sum(1 for n in self.nodes.values() if n.node_type == 'position_zone')
        }

