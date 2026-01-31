from routingAbstractions import AbstractRoutingDaemon
from packet import RoutingPacket, Payload

class EGP(AbstractRoutingDaemon):

    def __init__(self):
        super().__init__()
        self._id = None
        self._ip = None
        self._fwd_table = None
        self._asn = None
        self.DEBUG = False

        self._interface_relations = {}
        self._ip_to_iface = {}
        self._received_routes = {}
        self._best_routes = {}
        self._advertised_routes = {}
        self._dests_with_new_route = set()
        
        # Store revenue strings: "interface_name" -> "val" or "X;Y"
        self._interface_revenues = {}

    def dbg(self, msg):
        if self.DEBUG:
            print(f"[EGP-DEBUG] {self._id}: {msg}")

    def setParameters(self, parameters):
        self._asn = parameters['AS-ID'] 
        self._interface_relations = parameters['relations']
        self._ip_to_iface = {ip: iface for iface, ip in parameters['neighbours'].items()}
        
        # Try to capture initial revenues if passed (implementation specific)
        if 'link_properties' in parameters:
            self._interface_revenues = parameters['link_properties']

        for iface in self._interface_relations:
            neighbor_ip = parameters['neighbours'][iface]
            self._received_routes[neighbor_ip] = {}
            self._advertised_routes[iface] = {}

    def bindToRouter(self, router_id, router_ip, fwd_table):
        self._id = router_id
        self._ip = router_ip
        self._fwd_table = fwd_table

    def update(self, interfaces2state, currentTime):
        pass

    # --- NEW: Handle Dynamic Link Property Changes ---
    def update_link_properties(self, iface, properties):
        """Called by the simulator when link properties change (e.g. Time 10)"""
        if 'revenues' in properties:
            self.dbg(f"Updating revenues for {iface}: {properties['revenues']}")
            self._interface_revenues[iface] = properties['revenues']
            
            # Re-evaluate all routes because metrics have changed
            for dest in list(self._best_routes.keys()):
                self._select_best_route(dest)

    def processRoutingPacket(self, packet, iface):
        speaker_ip = None
        processed_dests = set()
        
        for data in packet.getPayload().getData():
            if data.startswith('speaker'):
                speaker_ip = data.split()[1]
            elif data.startswith('EGP-update'):
                parts = data.split()
                dest = parts[2]
                aspath_str = " ".join(parts[4:])

                if speaker_ip and dest not in processed_dests:
                    processed_dests.add(dest)
                    # Loop Detection
                    if self._asn in aspath_str.split():
                        if dest in self._received_routes[speaker_ip]:
                            self._received_routes[speaker_ip].pop(dest)
                            self._select_best_route(dest)
                        continue

                    new_aspath = f"{self._asn} {aspath_str}"
                    self._received_routes[speaker_ip][dest] = new_aspath
                    self._select_best_route(dest)
            elif data.startswith("EGP-withdrawal"):
                dest = data.split()[2]
                if speaker_ip and dest in self._received_routes[speaker_ip] and dest not in processed_dests:
                    processed_dests.add(dest)
                    self._received_routes[speaker_ip].pop(dest)
                    self._select_best_route(dest)

    def _get_route_metrics(self, dest, neighbor_ip, aspath):
        iface = self._ip_to_iface.get(neighbor_ip)
        relation = self._interface_relations.get(iface)
        revenue_str = self._interface_revenues.get(iface)
        
        # --- UNIFIED FINANCIAL METRIC ---
        # Instead of fixed constants (20000, 10000), we use the actual projected revenue.
        # This allows a high-paying Advanced Peer to beat a low-paying Customer.
        
        financial_score = 0
        
        # 1. Determine Revenue Value
        if revenue_str:
            try:
                if relation == 'advanced-peer':
                    # Format "X;Y". 
                    # X = Revenue if Ingress > Egress.
                    # Y = Revenue if Egress > Ingress.
                    # Route selection adds Egress traffic, pushing balance towards Y.
                    # Thus, the marginal value of the route is Y.
                    parts = revenue_str.split(';')
                    Y = int(parts[1].strip())
                    financial_score = Y
                else:
                    # Format "+4" or "-4"
                    financial_score = int(revenue_str.strip().replace('+', ''))
            except Exception:
                # Fallback defaults if parsing fails
                if relation == 'customer': financial_score = 4
                elif relation == 'provider': financial_score = -1
                
        else:
            # Defaults if no revenue string found (e.g. initial config missing)
            if relation == 'customer': financial_score = 4
            elif relation == 'provider': financial_score = -1
            elif relation == 'advanced-peer': financial_score = 0 # Assume neutral if unknown
            else: financial_score = 0 # Standard peer

        aslen = len(aspath.split())
        
        # Tie-breaker bias: Prefer Customer > Peer > Provider if revenues are identical
        # We add a tiny fraction to ensuring stability
        type_bias = 0
        if relation == 'customer': type_bias = 0.3
        elif relation == 'advanced-peer': type_bias = 0.2
        elif relation == 'peer': type_bias = 0.1
        
        final_metric = financial_score + type_bias

        return final_metric, aslen, relation, iface

    def _select_best_route(self, dest):
        best_path_data = None
        best_metric = -float('inf')
        best_aslen = float('inf')
        
        for neighbor_ip, routes in self._received_routes.items():
            if dest in routes:
                aspath = routes[dest]
                metric, aslen, relation, iface = self._get_route_metrics(dest, neighbor_ip, aspath)
                
                is_better = False
                
                # 1. Maximize Financial Metric
                if metric > best_metric:
                    is_better = True
                # 2. Tie-breaker: Shortest AS Path
                elif metric == best_metric and aslen < best_aslen:
                    is_better = True

                if is_better:
                    best_metric = metric
                    best_aslen = aslen
                    best_path_data = (aspath, neighbor_ip, iface, relation)

        current_best = self._best_routes.get(dest)

        if best_path_data:
            if not current_best or current_best[0] != best_path_data[0]:
                self._best_routes[dest] = best_path_data
                outgoing_iface = best_path_data[2]
                self._fwd_table.setEntry(dest, [outgoing_iface])
                self._dests_with_new_route.add(dest)
        elif current_best:
            self._best_routes.pop(dest)
            self._fwd_table.removeEntry(dest)
            self._dests_with_new_route.add(dest)

    def _build_packet(self, announce, withdraw):
        if not announce and not withdraw:
            return None
        pkt = RoutingPacket(self._ip)
        payload = Payload()
        payload.addEntry(f"speaker: {self._ip}")
        for d in announce:
            aspath = self._best_routes[d][0]
            payload.addEntry(f"EGP-update prefix: {d} AS-path: {aspath}")
        for d in withdraw:
            payload.addEntry(f"EGP-withdrawal prefix: {d}")
        pkt.setPayload(payload)
        return pkt

    def generateRoutingPacket(self, iface):
        relation = self._interface_relations.get(iface)
        if not relation:
            return None
            
        to_announce = []
        to_withdraw = []
        
        for dest, best in self._best_routes.items():
            aspath, _, _, learned_from = best
            
            # Export Rules (Policy):
            # 1. To Customer: Advertise EVERYTHING.
            # 2. To Peer/Provider/AdvPeer: Advertise ONLY Customer routes.
            valid = False
            if relation == 'customer':
                valid = True
            elif learned_from == 'customer':
                valid = True
            
            last = self._advertised_routes[iface].get(dest)
            if valid:
                if dest in self._dests_with_new_route or last != aspath:
                    to_announce.append(dest)
                    self._advertised_routes[iface][dest] = aspath
            else:
                if last:
                    to_withdraw.append(dest)
                    self._advertised_routes[iface].pop(dest)

        # Cleanup stale
        for dest in list(self._advertised_routes[iface].keys()):
            if dest not in self._best_routes:
                to_withdraw.append(dest)
                self._advertised_routes[iface].pop(dest)
            
        return self._build_packet(to_announce, to_withdraw)