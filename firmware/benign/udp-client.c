/*
 * AirGuard-6LoWPAN instrumented UDP client for Contiki-NG RPL Lite.
 *
 * Produces two machine-readable record types:
 *   AIRGUARD_EVENT  - application/routing events
 *   AIRGUARD_METRIC - 10-second cross-layer snapshots
 */

#include "contiki.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl.h"
#include "net/netstack.h"
#include "net/ipv6/simple-udp.h"
#include "net/link-stats.h"
#include "random.h"
#include "sys/energest.h"
#include "sys/node-id.h"

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "sys/log.h"
#define LOG_MODULE "AirGuard"
#define LOG_LEVEL LOG_LEVEL_INFO

#define UDP_CLIENT_PORT       8765
#define UDP_SERVER_PORT       5678
#define SEND_INTERVAL         (10 * CLOCK_SECOND)
#define PARENT_POLL_INTERVAL  CLOCK_SECOND
#define METRIC_INTERVAL_SEC   10

static struct simple_udp_connection udp_conn;

static uint32_t app_tx_count;
static uint32_t app_rx_count;
static uint32_t app_timeout_count;
static uint32_t route_miss_count;
static uint32_t parent_change_count;

static uint32_t last_tx_seq;
static clock_time_t last_tx_time;
static int32_t last_rtt_ms = -1;
static bool response_pending;

static bool parent_state_initialized;
static bool last_parent_present;
static linkaddr_t last_parent_addr;

/*---------------------------------------------------------------------------*/
static unsigned long
simulation_time_ms(void)
{
  return (unsigned long)(((uint64_t)clock_time() * 1000ULL) / CLOCK_SECOND);
}
/*---------------------------------------------------------------------------*/
static int
parent_id_from_lladdr(const linkaddr_t *addr)
{
  if(addr == NULL) {
    return -1;
  }

  return (int)addr->u8[LINKADDR_SIZE - 1]
       + ((int)addr->u8[LINKADDR_SIZE - 2] << 8);
}
/*---------------------------------------------------------------------------*/
static void
poll_parent_state(void)
{
  rpl_nbr_t *parent = curr_instance.dag.preferred_parent;
  const linkaddr_t *current_addr = NULL;
  bool current_present = false;

  if(parent != NULL) {
    current_addr = rpl_neighbor_get_lladdr(parent);
    current_present = current_addr != NULL;
  }

  if(!parent_state_initialized) {
    parent_state_initialized = true;
    last_parent_present = current_present;
    if(current_present) {
      linkaddr_copy(&last_parent_addr, current_addr);
    }
    return;
  }

  if(current_present != last_parent_present
     || (current_present && !linkaddr_cmp(current_addr, &last_parent_addr))) {
    int old_parent_id = last_parent_present
      ? parent_id_from_lladdr(&last_parent_addr) : -1;
    int new_parent_id = current_present
      ? parent_id_from_lladdr(current_addr) : -1;

    parent_change_count++;
    LOG_INFO("AIRGUARD_EVENT,event=parent_change,node=%u,time_ms=%lu,"
             "old_parent_id=%d,new_parent_id=%d,parent_changes=%" PRIu32 "\n",
             node_id, simulation_time_ms(), old_parent_id, new_parent_id,
             parent_change_count);

    last_parent_present = current_present;
    if(current_present) {
      linkaddr_copy(&last_parent_addr, current_addr);
    }
  }
}
/*---------------------------------------------------------------------------*/
static void
print_cross_layer_metric(void)
{
  rpl_nbr_t *parent = curr_instance.dag.preferred_parent;
  const linkaddr_t *parent_addr = NULL;
  const struct link_stats *stats = NULL;
  int parent_id = -1;
  int32_t etx_x100 = -1;
  int32_t rssi = LINK_STATS_RSSI_UNKNOWN;
  uint32_t mac_tx_attempts = 0;
  uint32_t mac_acked = 0;
  uint32_t mac_rx = 0;
  uint32_t queue_drops = 0;
  uint16_t etx_raw = 0;

  if(parent != NULL) {
    parent_addr = rpl_neighbor_get_lladdr(parent);
    stats = rpl_neighbor_get_link_stats(parent);
    parent_id = parent_id_from_lladdr(parent_addr);
  }

  if(stats != NULL) {
    etx_raw = stats->etx;
    rssi = stats->rssi;
    if(stats->etx > 0) {
      etx_x100 = (int32_t)(((uint32_t)stats->etx * 100U
                           + (LINK_STATS_ETX_DIVISOR / 2U))
                          / LINK_STATS_ETX_DIVISOR);
    }
#if LINK_STATS_PACKET_COUNTERS
    /* cnt_current is rolled into cnt_total only by link-stats' long-period
     * maintenance timer. Sum both so short AirGuard runs expose live
     * cumulative counters immediately and remain monotonic after rollover. */
    mac_tx_attempts = (uint32_t)stats->cnt_total.num_packets_tx
                    + (uint32_t)stats->cnt_current.num_packets_tx;
    mac_acked = (uint32_t)stats->cnt_total.num_packets_acked
              + (uint32_t)stats->cnt_current.num_packets_acked;
    mac_rx = (uint32_t)stats->cnt_total.num_packets_rx
           + (uint32_t)stats->cnt_current.num_packets_rx;
    queue_drops = (uint32_t)stats->cnt_total.num_queue_drops
                + (uint32_t)stats->cnt_current.num_queue_drops;
#endif
  }

  energest_flush();

  LOG_INFO("AIRGUARD_METRIC,role=client,node=%u,time_ms=%lu,reachable=%d,"
           "rank=%u,parent_id=%d,parent_changes=%" PRIu32 ",neighbors=%d,"
           "etx_raw=%u,etx_x100=%" PRId32 ",rssi=%" PRId32 ","
           "app_tx=%" PRIu32 ",app_rx=%" PRIu32 ",app_timeouts=%" PRIu32 ","
           "route_miss=%" PRIu32 ",pending=%d,last_rtt_ms=%" PRId32 ","
           "mac_tx_attempts=%" PRIu32 ",mac_acked=%" PRIu32 ","
           "mac_rx=%" PRIu32 ",queue_drops=%" PRIu32 ","
           "energest_cpu=%" PRIu64 ",energest_lpm=%" PRIu64 ","
           "energest_deep_lpm=%" PRIu64 ",energest_tx=%" PRIu64 ","
           "energest_listen=%" PRIu64 ",energest_total=%" PRIu64 "\n",
           node_id, simulation_time_ms(), NETSTACK_ROUTING.node_is_reachable(),
           curr_instance.dag.rank, parent_id, parent_change_count,
           rpl_neighbor_count(), etx_raw, etx_x100, rssi,
           app_tx_count, app_rx_count, app_timeout_count, route_miss_count,
           response_pending ? 1 : 0, last_rtt_ms,
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
  unsigned int payload_node = 0;
  unsigned long payload_seq = 0;
  uint16_t copy_len = datalen < sizeof(payload) - 1
    ? datalen : sizeof(payload) - 1;
  int parsed;
  int32_t rtt_ms = -1;

  memcpy(payload, data, copy_len);
  payload[copy_len] = '\0';
  parsed = sscanf(payload, "n=%u,s=%lu", &payload_node, &payload_seq);

  app_rx_count++;

  if(parsed == 2 && response_pending
     && payload_node == node_id
     && (uint32_t)payload_seq == last_tx_seq) {
    rtt_ms = (int32_t)(((uint64_t)(clock_time() - last_tx_time) * 1000ULL)
                       / CLOCK_SECOND);
    last_rtt_ms = rtt_ms;
    response_pending = false;
  }

  LOG_INFO("AIRGUARD_EVENT,event=app_rx,node=%u,time_ms=%lu,seq=%lu,"
           "rtt_ms=%" PRId32 ",payload_ok=%d,app_rx=%" PRIu32 "\n",
           node_id, simulation_time_ms(), payload_seq, rtt_ms,
           parsed == 2 ? 1 : 0, app_rx_count);
}
/*---------------------------------------------------------------------------*/
PROCESS(udp_client_process, "AirGuard UDP client");
PROCESS(airguard_client_metrics_process, "AirGuard client metrics");
AUTOSTART_PROCESSES(&udp_client_process, &airguard_client_metrics_process);
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(udp_client_process, ev, data)
{
  static struct etimer periodic_timer;
  static char payload[40];
  uip_ipaddr_t dest_ipaddr;

  PROCESS_BEGIN();

  simple_udp_register(&udp_conn, UDP_CLIENT_PORT, NULL,
                      UDP_SERVER_PORT, udp_rx_callback);

  LOG_INFO("AIRGUARD_BOOT,role=client,node=%u,time_ms=%lu,"
           "metric_interval_s=%u,send_interval_s=%lu\n",
           node_id, simulation_time_ms(), METRIC_INTERVAL_SEC,
           (unsigned long)(SEND_INTERVAL / CLOCK_SECOND));

  etimer_set(&periodic_timer, random_rand() % SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    if(NETSTACK_ROUTING.node_is_reachable()
       && NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {

      if(response_pending) {
        app_timeout_count++;
        LOG_INFO("AIRGUARD_EVENT,event=app_timeout,node=%u,time_ms=%lu,"
                 "seq=%" PRIu32 ",app_timeouts=%" PRIu32 "\n",
                 node_id, simulation_time_ms(), last_tx_seq,
                 app_timeout_count);
        response_pending = false;
      }

      last_tx_seq = app_tx_count;
      snprintf(payload, sizeof(payload), "n=%u,s=%" PRIu32,
               node_id, last_tx_seq);

      last_tx_time = clock_time();
      response_pending = true;
      app_tx_count++;

      LOG_INFO("AIRGUARD_EVENT,event=app_tx,node=%u,time_ms=%lu,"
               "seq=%" PRIu32 ",app_tx=%" PRIu32 "\n",
               node_id, simulation_time_ms(), last_tx_seq, app_tx_count);

      simple_udp_sendto(&udp_conn, payload, strlen(payload), &dest_ipaddr);
    } else {
      route_miss_count++;
      LOG_INFO("AIRGUARD_EVENT,event=route_unreachable,node=%u,time_ms=%lu,"
               "route_miss=%" PRIu32 "\n",
               node_id, simulation_time_ms(), route_miss_count);
    }

    etimer_set(&periodic_timer, SEND_INTERVAL
      - CLOCK_SECOND + (random_rand() % (2 * CLOCK_SECOND)));
  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(airguard_client_metrics_process, ev, data)
{
  static struct etimer poll_timer;
  static uint8_t elapsed_seconds;

  PROCESS_BEGIN();

  etimer_set(&poll_timer, PARENT_POLL_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&poll_timer));
    etimer_reset(&poll_timer);

    poll_parent_state();
    elapsed_seconds++;

    if(elapsed_seconds >= METRIC_INTERVAL_SEC) {
      elapsed_seconds = 0;
      print_cross_layer_metric();
    }
  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
