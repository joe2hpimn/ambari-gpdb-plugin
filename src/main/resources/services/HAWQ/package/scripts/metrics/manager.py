"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
from common import Utils
from query_stats import QueryMemoryStats

class StatsManager(object):
    def __init__(self, conn_params):
        self.conn_params = conn_params

    def run(self):
        merged_metrics = {}
        self.fill_query_memory_stats(merged_metrics)
        self.publish(merged_metrics)
        # self._debug_print(merged_metrics)

    def fill_query_memory_stats(self, merged_metrics):
        merged_metrics["query_memory"] = QueryMemoryStats(self.conn_params).get()

    def publish(self, merged_metrics):
        if merged_metrics:
            for (metric_group, stats) in merged_metrics.items():
                for stat in stats:
                    if stat.enabled:
                        Utils.publish_gmetric("/etc/ganglia/hdp/HDPSlaves/conf.d/gmond.slave.conf",
                                              stat.name, 
                                              stat.value, 
                                              stat.type_str)

    def _debug_print(self, merged_metrics):
        with open('/tmp/metrics.out', 'a') as f:
            for (metric_group, stats) in merged_metrics.items():
                f.write('\n')
                f.write(metric_group)
                f.write('\n')
                for stat in stats:
                    if stat.enabled:
                        f.write("{0}:{1}".format(stat.name, stat.value))
                        f.write('\n')

# code below is for local debugging only
if __name__=="__main__":
    import socket
    conn_params = dict(local_segment_hostname=socket.gethostname(), num_segments=2, connection_host="localhost", base_port=40000, dbname="template0", username="gpadmin")
    ag = StatsManager(conn_params=conn_params)
    ag.run()
