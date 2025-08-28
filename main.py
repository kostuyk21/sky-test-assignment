import time
from concurrent.futures import ThreadPoolExecutor, as_completed # ThreadPoolExecutor is good for task like api calls 
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Metrics
pods_scanned_total = Counter('pods_scanned_total', 'Total number of pods scanned')
pods_killed_total = Counter('pods_killed_total', 'Total number of pods killed')
scan_latency = Histogram('pod_scan_latency_seconds', 'Latency of scanning a pod')
kill_latency = Histogram('pod_kill_latency_seconds', 'Latency of killing a pod')
active_scans = Gauge('active_pod_scans', 'Number of pods currently being scanned')
error_count = Counter('pod_scan_errors_total', 'Total number of errors during pod scanning')
NUMBER_OF_PODS_IN_CLUSTER = 1000

class Pod: # Simple classes to mock k8s objects
    def __init__(self, namespace, name, node):
        self.namespace = namespace
        self.name = name
        self.node = node

class CiliumEndpoint:
    def __init__(self, namespace, name):
        self.namespace = namespace
        self.name = name


class KubernetesClient: #Mocked 
    def get_pods(self):
        return [Pod(namespace=f"namespace-{i//2}",name= f"pod-{i}", node=f"node-{i//3}" )for i in range(NUMBER_OF_PODS_IN_CLUSTER)]
    
    def delete_pod(self, namespace, name): # attributes of pod 
        time.sleep(2)
        print(f"Deleting pod {name} in {namespace}")

class CiliumClient:
    def __init__(self):
        self.endpoints = [CiliumEndpoint(namespace=f"namespace-{i//2}", name=f"pod-{i}") for i in range (0,NUMBER_OF_PODS_IN_CLUSTER,2)]

    def get_endpoint(self, namespace, name): # If no endpoint exists-> cilium not managing it
        for endpoint in self.endpoints:
            if endpoint.namespace == namespace and endpoint.name == name:
                return endpoint
        return None
    
class PodScanner:
    def __init__(self, k8s_client, cilium_client, max_workers):
        self.k8s_client = k8s_client
        self.cilium_client = cilium_client
        self.max_workers = max_workers  #  to prevent overwhelming of a system
        self.metrics_server_started = False
    
    def is_pod_managed_by_cilium(self, pod):
        with scan_latency.time(): #metric 
            endpoint = self.cilium_client.get_endpoint(pod.namespace, pod.name)
            if endpoint:
                return True
            return False
    def kill_pod(self, pod):
        try:
            with kill_latency.time():
                self.k8s_client.delete_pod(pod.namespace, pod.name)
                pods_killed_total.inc()
        except Exception as e:
            print(f"Failed to kill {pod.name} in {pod.namespace} due to {e}")
            error_count.inc()

    def process_pod(self, pod):
        try:
            active_scans.inc()
            pods_scanned_total.inc()
            if self.is_pod_managed_by_cilium(pod):
                print(f"Pod {[pod.name]} in {pod.namespace} namespace is managed by cilium")
            else:
                print(f"Pod {[pod.name]} in {pod.namespace} namespace is not managed by cilium. Killing it")
                self.kill_pod(pod)
        except Exception as e:
            print(f"Failed to kill {pod.name} in {pod.namespace} due to {e}")
            error_count.inc()
        finally:
            active_scans.dec()
       
        

    def scan_and_process_pods(self):
        """

        can be improved to process pods filtered by namespace
        """
        pods = self.k8s_client.get_pods()
        print(f"{len(pods)} pods will be processed")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.process_pod, pod) for pod in pods] #submit all tasks 
            for future in as_completed(futures): # iterate as task is finished
                try:
                    future.result()
                except Exception as e:
                    print(f"Task failed: {e}")

    def start_metrics_server(self, port = 8000):
        if not self.metrics_server_started:
            start_http_server(port)
            self.metrics_server_started = True
            print(f"Prometheus metrics server started on port {port}")
    
    def run(self):
        self.start_metrics_server()
        while True:
            try:
                self.scan_and_process_pods()
                print("Scan has completed")
                time.sleep(10) # Scan every 10 minutes? 
            except Exception as e:
                error_count.inc()
                print(f"Error in scanning : {e}")
                time.sleep(2)


if __name__ == "__main__":
    k8s_client = KubernetesClient()
    cilium_client = CiliumClient()
    scanner = PodScanner(k8s_client, cilium_client, 10)
    scanner.run()