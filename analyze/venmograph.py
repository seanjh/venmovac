from __future__ import division, absolute_import, print_function
import argparse
import os

from venmodb import client, db, trans_collection
import matplotlib.pyplot as plt
import networkx as nx
import graph_tool.all as gt
import numpy as np

parser = argparse.ArgumentParser(description='Venmo Social Graphing')
parser.add_argument('--infile', help='Load graph-tool graph from file')


class VenmoUser(object):
    def __init__(self, external_id, internal_id, username, first_name=None, last_name=None, full_name=None):
        self._external_id = int(external_id)
        self._internal_id = int(internal_id)
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.full_name = full_name

    @property
    def external_id(self):
        return self._external_id

    @property
    def internal_id(self):
        return self._internal_id

    def __hash__(self):
        return int(self.external_id)

    def __cmp__(self, other):
        return self.external_id.__cmp__(other.external_id)

    def __eq__(self, other):
        return self.external_id == other.external_id

    def __repr__(self):
        return "VenmoUser(%d, %d, username=%s)" % (
            self._external_id,
            self._internal_id,
            self.username
        )

    def __str__(self):
        return "VenmoUser %s (%d, %d)" % (
            self.username,
            self._external_id,
            self._internal_id
        )


# class VenmoTransaction(object):
#     # message
#     # source
#     # datetime
#     # payment_id
#     # story_id
#     # object_id
#     pass


def get_user(user_dict):
    if user_dict:
        return VenmoUser(
            user_dict.get('external_id'),
            user_dict.get('id'),
            user_dict.get('username'),
            first_name=user_dict.get('firstname'),
            last_name=user_dict.get('lastname'),
            full_name=user_dict.get('name'),
        )
    else:
        return None

def get_users(document):
    return get_user(document.get('payer')), get_user(document.get('payee'))


def get_transactions_cursor():
    search_terms = [
        'rent', 'bills', 'utilities', 'bill', 'water', 'cable', 'internet'
    ]
    pipeline = [
        # {"$match": {"$text": {"$search": ' '.join(search_terms)}}},
        {"$match": {"actor.external_id": { "$exists": True }}},
        {"$match": {"transactions.0.target.external_id": {"$exists": True }}},
        {"$unwind": "$transactions"},
        {"$project": {
            "payer": "$actor",
            "payee": "$transactions.target"
        }},
        {"$out": "tmp_transaction_pairs"}
        # {"$limit": 1000}
    ]

    cursor = trans_collection.aggregate(pipeline)

    pairs_collection = db['tmp_transaction_pairs']
    cursor = pairs_collection.find()
    print('Total results: %d' % cursor.count())
    return cursor

def build_graph_networkx(cursor):
    graph = nx.Graph()
    users_list = []
    for result in cursor:
        u1, u2 = get_users(result)
        graph.add_edge(u1, u2)

    return graph

def build_new_graph_gt(results_iter):
    graph = gt.Graph(directed=False)

    graph.vertex_properties['external_id'] = graph.new_vertex_property('int64_t')
    graph.vertex_properties['internal_id'] = graph.new_vertex_property('int64_t')
    graph.vertex_properties['username'] = graph.new_vertex_property('string')
    graph.edge_properties['transactions'] = graph.new_edge_property('int')

    users = {}

    for result in results_iter:
        u1, u2 = get_users(result)
        v1 = get_vertex_gt(users, u1, graph)
        v2 = get_vertex_gt(users, u2, graph)
        e = set_edge_gt(v1, v2, graph)

    return graph


def load_graph_file(filename):
    graph = gt.load_graph(filename)
    graph.set_directed(False)
    return graph

def get_vertex_gt(users, one_user, graph):
    key = one_user.external_id
    vertex = users.get(key)
    if not vertex:
        vertex = graph.add_vertex()
        graph.vp['external_id'][vertex] = one_user.external_id
        graph.vp['internal_id'][vertex] = one_user.internal_id
        graph.vp['username'][vertex] = one_user.username
        users[key] = vertex
    return vertex

def set_edge_gt(vertex_1, vertex_2, graph):
    edge_set_1 = set(vertex_1.all_edges())
    edge_set_2 = set(vertex_2.all_edges())
    common_edges = edge_set_1.intersection(edge_set_2)
    edge = None
    if not common_edges:
        edge = graph.add_edge(vertex_1, vertex_2)
        # Initialize the transactions value (i.e., edge weight)
        graph.ep['transactions'][edge] = 1
    else:
        edge = common_edges.pop()
        # Increment the transactions value (i.e., edge weight)
        graph.ep['transactions'][edge] += 1
    return edge

def subgraph_from_mst(graph, mst):
    filtered = gt.GraphView(graph, efilt=mst, directed=False)

    v_filter = filtered.new_vertex_property('bool')
    for edge in filtered.edges():
        source = edge.source()
        v_filter[source] = 1
        for vertex in source.all_neighbours():
            v_filter[vertex] = 1

        target = edge.target()
        v_filter[target] = 1
        for vertex in target.all_neighbours():
            v_filter[vertex] = 1

    filtered.set_vertex_filter(v_filter)

    return filtered


class VenmoVisitor(gt.BFSVisitor):
    def __init__(self, visited, vfilt, efilt, vertices=0, edges=0):
        self.visited = visited
        self.vfilt = vfilt
        self.efilt = efilt
        self.vertex_count = vertices
        self.edge_count = edges

    def examine_vertex(self, u):
        self.visited[u] = True
        self.vfilt[u] = True
        self.vertex_count += 1

    def examine_edge(self, e):
        self.efilt[e] = True
        self.edge_count += 1


def bfs_ft(graph, vertex):
    vertex_filter = graph.new_vertex_property('bool')
    edge_filter = graph.new_edge_property('bool')
    visitor = VenmoVisitor(graph.vp["visited"], vertex_filter, edge_filter)
    gt.bfs_search(graph, vertex, visitor)
    return visitor.vfilt, visitor.efilt, visitor.vertex_count, visitor.edge_count


def get_largest_subgraph_mst(graph):
    min_span_tree = None
    filtered = None
    max_subgraph = None
    vcount = 0
    max_vcount = 0
    seen_vertices = set()

    for vertex in graph.vertices():
        if vertex not in seen_vertices:
            print('Finding MST from %s. ' % vertex, end='')
            min_span_tree = gt.min_spanning_tree(graph, root=vertex)
            filtered = subgraph_from_mst(graph, min_span_tree)
            seen_vertices = seen_vertices.union(filtered.vertices())
            # edge_count = np.count_nonzero(min_span_tree.get_array())
            print(" MST saw %d vertices and %d edges                      \r" % (filtered.num_vertices(), filtered.num_edges()), end='')
            if filtered.num_vertices() > max_vcount:
                max_vcount = filtered.num_vertices()
                max_subgraph = subgraph_from_mst(graph, min_span_tree)
                print("New maximal subgraph with %d vertices and %d edges\n" % (
                    max_subgraph.num_vertices(), max_subgraph.num_edges()
                ))
        else:
            pass

    print('Original graph includes %d total vertices and %d total edges' % (
        graph.num_vertices(), graph.num_edges())
    )
    print(('Edge & Vertex filtered graph includes %d total vertices and '
        '%d total edges') % (
        max_subgraph.num_vertices(), max_subgraph.num_edges()
    ))

    return max_subgraph


def get_largest_subgraph_bfs(graph):
    max_subgraph = None
    max_vcount = 0

    graph.vertex_properties["visited"] = graph.new_vertex_property('bool')
    for vertex in graph.vertices():
        if not graph.vp["visited"][vertex]:
            graph.vp["visited"][vertex] = True
            print('Conducting BFS from %s. ' % vertex, end='')
            vfilt, efilt, vcount, ecount = bfs_ft(graph, vertex)
            print(" BFS saw %d vertices and %d edges                \r" % (vcount, ecount), end='')
            if vcount > max_vcount:
                max_vcount = vcount
                max_subgraph = gt.GraphView(graph, vfilt=vfilt, efilt=efilt, directed=False)
                print("New maximal subgraph with %d vertices and %d edges\n" % (
                    max_subgraph.num_vertices(), max_subgraph.num_edges()
                ))
        else:
            pass

    print('Original graph includes %d total vertices and %d total edges' % (
        graph.num_vertices(), graph.num_edges())
    )
    print(('Edge & Vertex filtered graph includes %d total vertices and '
        '%d total edges') % (
        max_subgraph.num_vertices(), max_subgraph.num_edges()
    ))

    return max_subgraph


def draw_sfdp_graph(graph, filename):
    x = raw_input("Press enter to save graph to %s..." % filename)
    pos = gt.sfdp_layout(graph)
    bv, be = gt.betweenness(graph)
    be.a /= be.a.max() / 5
    deg = graph.degree_property_map("total")
    gt.graph_draw(
        graph,
        pos=pos,
        vertex_fill_color=bv,
        edge_pen_width=be,
        output=filename
    )

def main():
    args = parser.parse_args()
    if args.infile and not not os.path.exists(os.path.abspath(args.infile)):
        raise IOError("Unable to locate file %s" % args.infile)

    graph = None
    if args.infile:
        print("Loading graph from file %s" % args.infile)
        graph = load_graph_file(args.infile)
    else:
        print("Loading graph from database")
        cursor = get_transactions_cursor()
        graph = build_new_graph_gt(cursor)

    print("Graph has %d vertices and %d edges" % (graph.num_vertices(), graph.num_edges()))

    graph.save("full_graph.xml.gz")

    # filtered = get_largest_subgraph_bfs(graph)
    filtered = get_largest_subgraph_mst(graph)
    filtered.save("filtered_graph.xml.gz")
    # outfile = os.path.join(os.path.expanduser("~"), 'graph-draw.pdf')
    outfile = 'venmo.pdf'
    draw_sfdp_graph(filtered, outfile)

if __name__ == '__main__':
    main()
