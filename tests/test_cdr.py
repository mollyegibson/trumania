from __future__ import division

import time
from datetime import datetime
import json

from bi.ria.generator.action import *
from bi.ria.generator.clock import *
from bi.ria.generator.circus import *
from bi.ria.generator.product import *
from bi.ria.generator.random_generators import *
from bi.ria.generator.relationship import *
from bi.ria.generator.util_functions import *

from bi.ria.generator.actor import *


def compose_circus():
    """
        Builds a circus simulating call, mobility and topics.
        See test case below
    """

    ######################################
    # Define parameters
    ######################################
    tp = time.clock()
    print "Parameters"

    seed = 123456
    n_customers = 1000
    n_cells = 100
    n_agents = 100
    average_degree = 20

    prof = pd.Series([5., 5., 5., 5., 5., 3., 3.],
                     index=[timedelta(days=x, hours=23, minutes=59, seconds=59) for x in range(7)])
    time_step = 60

    mov_prof = pd.Series(
        [1., 1., 1., 1., 1., 1., 1., 1., 5., 10., 5., 1., 1., 1., 1., 1., 1., 5., 10., 5., 1., 1., 1., 1.],
        index=[timedelta(hours=h, minutes=59, seconds=59) for h in range(24)])

    cells = ["CELL_%s" % (str(i).zfill(4)) for i in range(n_cells)]
    agents = ["AGENT_%s" % (str(i).zfill(3)) for i in range(n_agents)]

    products = ["VOICE", "SMS"]

    print "Done"

    ######################################
    # Define clocks
    ######################################
    tc = time.clock()
    print "Clock"
    the_clock = Clock(datetime(year=2016, month=6, day=8), time_step, "%d%m%Y %H:%M:%S", seed)
    print "Done"

    ######################################
    # Define generators
    ######################################
    tg = time.clock()
    print "Generators"
    msisdn_gen = MSISDNGenerator("msisdn-tests-1", "0032", ["472", "473", "475", "476", "477", "478", "479"], 6, seed)
    activity_gen = GenericGenerator("user-activity", "pareto", {"a": 1.2, "m": 10.}, seed)
    timegen = WeekProfiler(time_step, prof, seed)

    mobilitytimegen = DayProfiler(time_step, mov_prof, seed)
    networkchooser = WeightedChooserAggregator("B", "weight", seed)
    networkweightgenerator = GenericGenerator("network-weight", "pareto", {"a": 1.2, "m": 1.}, seed)

    mobilitychooser = WeightedChooserAggregator("CELL", "weight", seed)
    mobilityweightgenerator = GenericGenerator("mobility-weight", "exponential", {"scale": 1.})

    agentchooser = WeightedChooserAggregator("AGENT", "weight", seed)
    agentweightgenerator = GenericGenerator("agent-weight", "exponential", {"scale": 1.})

    init_mobility_generator = GenericGenerator("init-mobility", "choice", {"a": cells})

    SMS_price_generator = GenericGenerator("SMS-price", "constant", {"a": 10.})
    voice_duration_generator = GenericGenerator("voice-duration", "choice", {"a": range(20, 240)}, seed)
    voice_price_generator = ValueGenerator("voice-price", 1)
    productchooser = WeightedChooserAggregator("PRODUCT", "weight", seed)

    recharge_init = GenericGenerator("recharge init", "constant", {"a": 1000.})
    recharge_trigger = TriggerGenerator("Topup", "logistic", {}, seed)
    print "Done"

    ######################################
    # Initialise generators
    ######################################
    tig = time.clock()
    print "initialise Time Generators"
    timegen.initialise(the_clock)
    mobilitytimegen.initialise(the_clock)
    print "Done"

    ######################################
    # Define Actors, Relationships, ...
    ######################################
    tcal = time.clock()
    print "Create callers"
    customers = Actor(n_customers)
    print "Done"
    tatt = time.clock()
    customers.gen_attribute(name="MSISDN",
                            generator=msisdn_gen)
    # customers.gen_attribute("activity", activity_gen)
    # customers.gen_attribute("clock", timegen, weight_field="activity")

    print "Added atributes"
    tsna = time.clock()
    print "Creating social network"
    social_network = create_er_social_network(customers.get_ids(), float(average_degree) / float(n_customers), seed)
    tsnaatt = time.clock()
    print "Done"
    network = WeightedRelationship("A", "B", networkchooser)
    network.add_relation("A", social_network["A"].values, "B", social_network["B"].values,
                         networkweightgenerator.generate(len(social_network.index)))
    network.add_relation("A", social_network["B"].values, "B", social_network["A"].values,
                         networkweightgenerator.generate(len(social_network.index)))
    print "Done SNA"
    tmo = time.clock()
    print "Mobility"
    mobility_df = pd.DataFrame.from_records(make_random_bipartite_data(customers.get_ids(), cells, 0.4, seed),
                                            columns=["A", "CELL"])
    print "Network created"
    tmoatt = time.clock()
    mobility = WeightedRelationship("A", "CELL", mobilitychooser)
    mobility.add_relation("A", mobility_df["A"], "CELL", mobility_df["CELL"],
                          mobilityweightgenerator.generate(len(mobility_df.index)))

    customers.add_transient_attribute(name="CELL",
                                      att_type="choice",
                                      generator=init_mobility_generator)

    agent_df = pd.DataFrame.from_records(make_random_bipartite_data(customers.get_ids(), agents, 0.3, seed),
                                         columns=["A", "AGENT"])
    print "Agent relationship created"
    tagatt = time.clock()
    agent_rel = AgentRelationship("A", "AGENT", agentchooser)
    agent_rel.add_relation("A", agent_df["A"], "AGENT", agent_df["AGENT"],
                           agentweightgenerator.generate(len(agent_df.index)))

    customers.add_transient_attribute(name="MAIN_ACCT",
                                      att_type="stock",
                                      generator=recharge_init,
                                      params={"trigger_generator":
                                                  recharge_trigger})
    print "Done all customers"

    voice = VoiceProduct(voice_duration_generator, voice_price_generator)
    sms = SMSProduct(SMS_price_generator)

    product_df = assign_random_proportions("A", "PRODUCT", customers.get_ids(), products, seed)
    product_rel = ProductRelationship("A", "PRODUCT", productchooser, {"VOICE": voice, "SMS": sms})
    product_rel.add_relation("A", product_df["A"], "PRODUCT", product_df["PRODUCT"], product_df["weight"])

    ######################################
    # Create circus
    ######################################
    tci = time.clock()
    print "Creating circus"
    flying = Circus(the_clock)
    flying.add_actor("customers", customers)
    flying.add_relationship("A", "B", network)
    flying.add_generator("time", timegen)
    flying.add_generator("networkchooser", networkchooser)

    topup = AttributeAction(name="topup",
                            actor=customers,
                            field="MAIN_ACCT",
                            activity_generator=GenericGenerator("1",
                                                                "constant",
                                                                {"a":1.}),
                            time_generator=ConstantProfiler(-1),
                            parameters={"relationship": agent_rel,
                                         "id1": "A",
                                         "id2": "AGENT",
                                         "id3": "value"}
                            )

    calls = ActorAction("calls", customers, timegen, activity_gen)
    calls.add_relationship("network", network)
    calls.add_relationship("product", product_rel)
    calls.add_field("B", "network", {"key": "A"})
    calls.add_field("PRODUCT", "product", {"key": "A"})
    calls.add_impact("value decrease", "MAIN_ACCT", "decrease_stock", {"value": "VALUE", "key": "A","recharge_action":topup})

    mobility = AttributeAction(name="mobility",
                               actor=customers,
                               field="CELL",
                               activity_generator=GenericGenerator("1",
                                                                     "constant",
                                                                     {"a":1.}),
                               time_generator=mobilitytimegen,
                               parameters={'relationship': mobility,
                                           'new_time_generator': mobilitytimegen,
                                           'id1': "A",
                                           'id2': "CELL"})

    flying.add_action(calls, {"join": [("A", customers, "MSISDN", "A_NUMBER"),
                                       ("B", customers, "MSISDN", "B_NUMBER"),
                                       ("A", customers, "CELL", "CELL_A"),
                                       ("B", customers, "CELL", "CELL_B"), ]})

    flying.add_action(mobility)

    flying.add_action(topup, {"join": [("A", customers, "MSISDN", "CUSTOMER_NUMBER"),
                                       ("A", customers, "CELL", "CELL")]})

    flying.add_increment(timegen)
    tr = time.clock()

    print "Done"

    all_times = {"parameters": tc - tp,
                 "clocks": tg - tc,
                 "generators": tig - tg,
                 "init generators": tcal - tig,
                 "callers creation (full)": tmo - tcal,
                 "caller creation (solo)": tatt - tcal,
                 "caller attribute creation": tsna - tatt,
                 "caller SNA graph creation": tsnaatt - tsna,
                 "mobility graph creation": tmoatt - tmo,
                 "mobility attribute creation": tci - tmoatt,
                 "circus creation": tr - tci,
                 "tr": tr,
        }

    return flying, all_times


def test_cdr_scenario():

    cdr_circus, all_times = compose_circus()
    n_iterations = 100

    all_cdrs, all_mov, all_topup = cdr_circus.run(n_iterations)
    tf = time.clock()

    all_times["runs (all)"] = tf - all_times["tr"]
    all_times["one run (average)"] = (tf - all_times["tr"]) / n_iterations

    print (json.dumps(all_times, indent=2))

    assert all_cdrs.shape[0] > 0
    assert "datetime" in all_cdrs.columns

    assert all_mov.shape[0] > 0
    assert "datetime" in all_mov.columns

    assert all_topup.shape[0] > 0
    assert "datetime" in all_topup.columns

    print ("""
        some cdrs:
          {}

        some mobility events:
          {}

        some topup event:
          {}

    """.format(all_cdrs.head(), all_mov.head(), all_topup.head()))

    # TODO: add real post-conditions on all_cdrs, all_mov and all_topus

