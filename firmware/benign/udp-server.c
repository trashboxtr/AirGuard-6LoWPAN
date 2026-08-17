/*
 * AirGuard-6LoWPAN instrumented UDP/RPL root for Contiki-NG RPL Lite.
 *
 * Produces two machine-readable record types:
 *   AIRGUARD_EVENT  - server receive/transmit events
 *   AIRGUARD_METRIC - 10-second cross-layer root snapshots
 */

#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"
#include "net/netstack.h"
#include "net/ipv6/simple-udp.h"
#include "net/link-stats.h"
#include "net/nbr-table.h"
#include "sys/energest.h"
#include "sys/node-id.h"

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "sys/log.h"
#define LOG_MODULE "AirGuard"
#define LOG_LEVEL LOG_LEVEL_INFO

#define UDP_CLIENT_PORT      8765
#define UDP_SERVER_PORT      5678
#define METRIC_INTERVAL      (10 * CLOCK_SECOND)

static struct simple_udp_connection udp_conn;
static uint32_t server_rx_count;
static uint32_t server_tx_count;

/*---------------------------------------------------------------------------*/
static unsigned long
simulation_time_ms(void)
{
  return (unsigned long)(((uint64_t)clock_time() * 1000ULL) / CLOCK_SECOND);
}
/*---------------------------------------------------------------------------*/
static void
print_root_metric(void)
{
  rpl_nbr_t *nbr;
  uint32_t mac_tx_attempts = 0;
  uint32_t mac_acked = 0;
  uint32_t mac_rx = 0;
  uint32_t queue_drops = 0;
  uint32_t etx_sum = 0;
  int32_t rssi_sum = 0;
  uint16_t etx_samples = 0;
  uint16_t rssi_samples = 0;
  int32_t mean_etx_x100 = -1;
  int32_t mean_rssi = LINK_STATS_RSSI_UNKNOWN;

  for(nbr = nbr_table_head(rpl_neighbors);
      nbr != NULL;
      nbr = nbr_table_next(rpl_neighbors, nbr)) {
    const struct link_stats *stats = rpl_neighbor_get_link_stats(nbr);

    if(stats == NULL) {
      continue;
    }

    if(stats->etx > 0) {
      etx_sum += stats->etx;
      etx_samples++;
    }

    if(stats->rssi != LINK_STATS_RSSI_UNKNOWN) {
      rssi_sum += stats->rssi;
      rssi_samples++;
    }

#if LINK_STATS_PACKET_COUNTERS
    /* cnt_current is rolled into cnt_total only by link-stats' long-period
     * maintenance timer. Sum both to expose live cumulative counters. */
    mac_tx_attempts += (uint32_t)stats->cnt_total.num_packets_tx
                     + (uint32_t)stats->cnt_current.num_packets_tx;
    mac_acked += (uint32_t)stats->cnt_total.num_packets_acked
               + (uint32_t)stats->cnt_current.num_packets_acked;
    mac_rx += (uint32_t)stats->cnt_total.num_packets_rx
            + (uint32_t)stats->cnt_current.num_packets_rx;
    queue_drops += (uint32_t)stats->cnt_total.num_queue_drops
                 + (uint32_t)stats->cnt_current.num_queue_drops;
#endif
  }

  if(etx_samples > 0) {
    mean_etx_x100 = (int32_t)(((uint64_t)etx_sum * 100ULL
                              + ((uint64_t)etx_samples
                                 * LINK_STATS_ETX_DIVISOR / 2ULL))
                             / ((uint64_t)etx_samples
                                * LINK_STATS_ETX_DIVISOR));
  }

  if(rssi_samples > 0) {
    mean_rssi = rssi_sum / rssi_samples;
  }

  energest_flush();

  LOG_INFO("AIRGUARD_METRIC,role=server,node=%u,time_ms=%lu,reachable=%d,"
           "rank=%u,parent_id=-1,parent_changes=0,neighbors=%d,"
           "mean_etx_x100=%" PRId32 ",mean_rssi=%" PRId32 ","
           "server_rx=%" PRIu32 ",server_tx=%" PRIu32 ","
           "mac_tx_attempts=%" PRIu32 ",mac_acked=%" PRIu32 ","
           "mac_rx=%" PRIu32 ",queue_drops=%" PRIu32 ","
           "energest_cpu=%" PRIu64 ",energest_lpm=%" PRIu64 ","
           "energest_deep_lpm=%" PRIu64 ",energest_tx=%" PRIu64 ","
           "energest_listen=%" PRIu64 ",energest_total=%" PRIu64 "\n",
           node_id, simulation_time_ms(), NETSTACK_ROUTING.node_is_reachable(),
           curr_instance.dag.rank, rpl_neighbor_count(),
           mean_etx_x100, mean_rssi, server_rx_count, server_tx_count,
           mac_tx_attempts, mac_acked, mac_rx, queue_drops,
           energest_type_time(ENERGEST_TYPE_CPU),
           energest_type_time(ENERGEST_TYPE_LPM),
           energest_type_time(ENERGEST_TYPE_DEEP_LPM),
           energest_type_time(ENERGEST_TYPE_TRANSMIT),
           energest_type_time(ENERGEST_TYPE_LISTEN),
           ENERGEST_GET_TOTAL_TIME());
}
/*---------------------------------------------------------------------------*/
static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  char payload[40];
  unsigned int source_node = 0;
  unsigned long sequence = 0;
  uint16_t copy_len = datalen < sizeof(payload) - 1
    ? datalen : sizeof(payload) - 1;
  int parsed;

  memcpy(payload, data, copy_len);
  payload[copy_len] = '\0';
  parsed = sscanf(payload, "n=%u,s=%lu", &source_node, &sequence);

  server_rx_count++;

  LOG_INFO("AIRGUARD_EVENT,event=server_rx,node=%u,time_ms=%lu,"
           "src_node=%u,seq=%lu,payload_ok=%d,server_rx=%" PRIu32 "\n",
           node_id, simulation_time_ms(), source_node, sequence,
           parsed == 2 ? 1 : 0, server_rx_count);

  simple_udp_sendto(&udp_conn, data, datalen, sender_addr);
  server_tx_count++;

  LOG_INFO("AIRGUARD_EVENT,event=server_tx,node=%u,time_ms=%lu,"
           "dst_node=%u,seq=%lu,server_tx=%" PRIu32 "\n",
           node_id, simulation_time_ms(), source_node, sequence,
           server_tx_count);
}
/*---------------------------------------------------------------------------*/
PROCESS(udp_server_process, "AirGuard UDP server");
PROCESS(airguard_server_metrics_process, "AirGuard server metrics");
AUTOSTART_PROCESSES(&udp_server_process, &airguard_server_metrics_process);
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(udp_server_process, ev, data)
{
  PROCESS_BEGIN();

  NETSTACK_ROUTING.root_start();

  simple_udp_register(&udp_conn, UDP_SERVER_PORT, NULL,
                      UDP_CLIENT_PORT, udp_rx_callback);

  LOG_INFO("AIRGUARD_BOOT,role=server,node=%u,time_ms=%lu,"
           "metric_interval_s=%lu\n",
           node_id, simulation_time_ms(),
           (unsigned long)(METRIC_INTERVAL / CLOCK_SECOND));

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(airguard_server_metrics_process, ev, data)
{
  static struct etimer metric_timer;

  PROCESS_BEGIN();

  etimer_set(&metric_timer, METRIC_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&metric_timer));
    etimer_reset(&metric_timer);
    print_root_metric();
  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
