/**
 * FOOD MAN - INDUSTRIAL FOOD MANUFACTURING & SUPPLY CHAIN MANAGEMENT
 * Master-Detail Architecture & State Management
 */

// Global Application State
const appState = {
  currentDomain: 'production', // 'production' | 'qc' | 'raw-materials' | 'inventory' | 'dispatch'
  currentFilter: 'all',        // 'all' | 'attention' | 'ready'
  searchQuery: '',
  selectedCardId: null,
  activeItem: null
};

// Domain Metadata & Display Configurations
const domainConfigs = {
  production: {
    title: "Production & Packaging Batches",
    breadcrumb: ["Home", "Factory", "Production Batches"],
    createBtnText: "+ New Production Batch",
    counterLabel: "batches running",
    unit: "Cartons",
    dropdown1Label: "Operating Status",
    dropdown1Options: [
      { value: "running", label: "In Production", pill: "amber" },
      { value: "qc_hold", label: "Pending QC Approval", pill: "amber" },
      { value: "completed", label: "Completed", pill: "green" },
      { value: "scheduled", label: "Scheduled Next Shift", pill: "blue" }
    ],
    dropdown2Label: "Filling Line",
    dropdown2Options: ["Line A1 - Tetra Pak 250ml", "Line A2 - PET Bottle 350ml", "Line B1 - Aluminum Can 330ml", "Line C - Aseptic Packaging"],
    dropdown3Label: "Shift Operations Lead",
    dropdown3Options: ["Tran Minh Quan", "Le Hai Dang", "Nguyen Thu Ha", "Vu Hoang Long"],
    dropdown4Label: "Temporary Storage Area",
    dropdown4Options: ["Central Cold Storage (Block A)", "Packaging Buffer Zone (Zone 2)", "Sterile Holding Silo #04", "Outbound Staging Area"]
  },
  qc: {
    title: "Quality Control (QC Review)",
    breadcrumb: ["Home", "Management", "QC Inspection"],
    createBtnText: "+ New Inspection Record",
    counterLabel: "samples pending",
    unit: "Parameters",
    dropdown1Label: "Inspection Conclusion",
    dropdown1Options: [
      { value: "pending", label: "Testing in Progress", pill: "amber" },
      { value: "passed", label: "Safety Standard Passed", pill: "green" },
      { value: "retest", label: "Retest Required (Microbiology)", pill: "amber" },
      { value: "rejected", label: "Specification Failed", pill: "red" }
    ],
    dropdown2Label: "Analytical Lab",
    dropdown2Options: ["Microbiology Lab #01", "Physicochemical Lab #02", "Sensory Testing Station", "Toxicology Lab"],
    dropdown3Label: "QC Specialist",
    dropdown3Options: ["MSc. Pham Thu Trang", "Eng. Do Duc Minh", "Vu Hoang Long", "Tran Minh Quan"],
    dropdown4Label: "Standards Applied",
    dropdown4Options: ["QCVN 5-1:2010/BYT", "ISO 22000:2018", "HACCP Grade A Standard", "FSSC 22000 v5.1"]
  },
  "raw-materials": {
    title: "Inbound Raw Material Lots",
    breadcrumb: ["Home", "Management", "Raw Materials"],
    createBtnText: "+ Inbound Material Lot",
    counterLabel: "lots in stock",
    unit: "kg",
    dropdown1Label: "Inspection Status",
    dropdown1Options: [
      { value: "inspected", label: "Inbound Approved", pill: "green" },
      { value: "sampling", label: "Sampling in Progress", pill: "amber" },
      { value: "quarantine", label: "Quarantine Monitoring", pill: "amber" },
      { value: "rejected", label: "Returned to Supplier", pill: "red" }
    ],
    dropdown2Label: "Raw Material Warehouse",
    dropdown2Options: ["Dry Aerated Silo A1", "Grain Silo B1", "Specialty Silo C3", "Quarantine Holding Buffer"],
    dropdown3Label: "Receiving Officer",
    dropdown3Options: ["Nguyen Thu Ha", "Le Hai Dang", "Do Duc Minh", "Tran Minh Quan"],
    dropdown4Label: "Supplier",
    dropdown4Options: ["Golden Grain & Oilseed Co.", "Sunrise Agri Seeds Corp.", "Central Plains Farm Collective"]
  },
  inventory: {
    title: "Finished Goods Warehouse Stock",
    breadcrumb: ["Home", "Warehouse", "Finished Goods Stock"],
    createBtnText: "+ Transfer Inventory",
    counterLabel: "items in stock",
    unit: "Pallets",
    dropdown1Label: "Stock Status",
    dropdown1Options: [
      { value: "in_stock", label: "Optimal Stock", pill: "green" },
      { value: "low_stock", label: "Near Minimum Safety Level", pill: "amber" },
      { value: "reserved", label: "Reserved for Large Contract", pill: "blue" },
      { value: "near_expiry", label: "Near Expiry - Urgent Dispatch", pill: "amber" }
    ],
    dropdown2Label: "Storage Bin",
    dropdown2Options: ["Aisle A - Rack 04 (Tier 3)", "Aisle B - Cold Storage Pallet", "Aisle C - FIFO Flow Rack", "Aisle D - Outbound Staging Area"],
    dropdown3Label: "Warehouse Manager",
    dropdown3Options: ["Hoang Dinh Tuan", "Nguyen Thu Ha", "Le Hai Dang", "Vu Hoang Long"],
    dropdown4Label: "Dispatch Policy",
    dropdown4Options: ["FEFO (Nearest Expiry First)", "FIFO (First In First Out)", "High Priority Contract", "Special Hold by Request"]
  },
  dispatch: {
    title: "Outbound Dispatch Orders & Logistics",
    breadcrumb: ["Home", "Logistics", "Dispatch Orders"],
    createBtnText: "+ Create Dispatch Order",
    counterLabel: "dispatch orders",
    unit: "Packages",
    dropdown1Label: "Dispatch Progress",
    dropdown1Options: [
      { value: "dispatched", label: "In Transit", pill: "green" },
      { value: "loading", label: "Loading in Progress", pill: "amber" },
      { value: "ready", label: "Packed & Awaiting Truck", pill: "green" },
      { value: "pending_doc", label: "Awaiting Shipping Documents", pill: "amber" }
    ],
    dropdown2Label: "Carrier / Fleet",
    dropdown2Options: ["Factory Reefer Fleet (Truck 04)", "Nam Ha Container Cold Logistics", "J&T Express Cold Logistics", "Viettel Post Transport Fleet"],
    dropdown3Label: "Driver / Supervisor",
    dropdown3Options: ["Driver Bui Van Hung", "Nguyen Van Thien (Truck 29C-8819)", "Le Van Hung", "Pham Van Tan"],
    dropdown4Label: "Delivery Destination",
    dropdown4Options: ["Mega Market Central DC Binh Phu", "VinMart Distribution Center Hanoi", "Cat Lai Seaport (Export Terminal)", "AEON Mall Long Bien Distribution"]
  }
};

// Rich Multi-Domain Datasets
const initialData = {
  production: [
    {
      id: "LOT-2026-089",
      category: "Oilseed Products",
      title: "Pure Roasted Peanut Oil 1L",
      statValue: "4,500 / 5,000",
      statSub: "Bottles completed",
      progress: 90,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Mfg Date / Shift", value: "08/09/2026 - Shift 1" },
        { label: "Line", value: "Line A1 - Bottling Line" },
        { label: "Press Temperature", value: "120.0°C" },
        { label: "Finished Expiry Date", value: "08/03/2027" }
      ],
      avatars: [
        { initial: "TM", bg: "#162B4E", name: "Tran Minh Quan" },
        { initial: "LH", bg: "#2563EB", name: "Le Hai Dang" },
        { initial: "NT", bg: "#059669", name: "Nguyen Thu Ha" }
      ],
      status: "running",
      statusLabel: "Bottling in Progress",
      statusPill: "amber",
      dropdown1: "running",
      dropdown2: "Line A1 - Tetra Pak 250ml",
      dropdown3: "Tran Minh Quan",
      dropdown4: "Central Cold Storage (Block A)",
      readOnlySpecs: [
        { label: "Free Fatty Acids", value: "0.18% (Spec <= 0.30%)", icon: "flask" },
        { label: "Peroxide Value", value: "1.4 meq/kg", icon: "activity" },
        { label: "Moisture & Volatile", value: "0.04%", icon: "check-circle" },
        { label: "Traceability QR Code", value: "LOT089-PNT-2026", icon: "qr-code", mono: true },
        { label: "Pressing Batch Number", value: "Expeller Unit #02", icon: "database" }
      ],
      timeline: [
        { time: "06:30 AM", desc: "Line sanitation and nitrogen purge verified" },
        { time: "07:15 AM", desc: "Started expeller screw pressing of Lot RAW-LOT-512" },
        { time: "08:00 AM", desc: "Bottled first 2,000 bottles" },
        { time: "10:45 AM", desc: "Mid-shift composite sample passed QC" }
      ],
      bannerType: "milk"
    },
    {
      id: "LOT-2026-090",
      category: "Oilseed Products",
      title: "Cold-Pressed Sunflower Seed Oil 1L",
      statValue: "12,000 / 12,000",
      statSub: "Bottles packaged",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Mfg Date / Shift", value: "07/09/2026 - Shift 2" },
        { label: "Line", value: "Line A2 - Cold Press" },
        { label: "Extraction Yield", value: "44.8% (Target >= 44.0%)" },
        { label: "Clarity Index", value: "Brilliant Amber" }
      ],
      avatars: [
        { initial: "VH", bg: "#D97706", name: "Vu Hoang Long" },
        { initial: "PT", bg: "#7C3AED", name: "Pham Thu Trang" }
      ],
      status: "completed",
      statusLabel: "Approved for Release",
      statusPill: "green",
      dropdown1: "completed",
      dropdown2: "Line B1 - Aluminum Can 330ml",
      dropdown3: "Vu Hoang Long",
      dropdown4: "Outbound Staging Area",
      readOnlySpecs: [
        { label: "Cold Press Temp", value: "42°C (True Cold Press)", icon: "flask" },
        { label: "Vitamin E Content", value: "48mg / 100g", icon: "activity" },
        { label: "Cap Seal Integrity", value: "100% Induction Sealed", icon: "check-circle" },
        { label: "Traceability QR Code", value: "SUN-1L-LOT90", icon: "qr-code", mono: true },
        { label: "Certification", value: "HACCP & ISO 22000 Certified", icon: "shield" }
      ],
      timeline: [
        { time: "Yesterday 14:00", desc: "Received sunflower seeds from Sunrise Agri" },
        { time: "Yesterday 18:30", desc: "Packaged 12,000 bottles" },
        { time: "Today 08:00", desc: "QC issued green release certificate" }
      ],
      bannerType: "juice"
    },
    {
      id: "LOT-2026-091",
      category: "Fermented Yogurt",
      title: "Aloe Vera Cup Yogurt 100g 4-Pack",
      statValue: "6,200 / 8,000",
      statSub: "Packs produced",
      progress: 77,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Incubation Time", value: "7.5 hours / 42°C" },
        { label: "Starter Culture", value: "L. Bulgaricus & S. Therm" },
        { label: "Line", value: "Line C - Cup Packaging" },
        { label: "Shelf Life", value: "45 days (Chilled 4°C)" }
      ],
      avatars: [
        { initial: "TM", bg: "#162B4E", name: "Tran Minh Quan" },
        { initial: "DM", bg: "#0D9488", name: "Do Duc Minh" }
      ],
      status: "qc_hold",
      statusLabel: "Incubation Microbial Check Pending",
      statusPill: "amber",
      dropdown1: "qc_hold",
      dropdown2: "Line C - Aseptic Packaging",
      dropdown3: "Tran Minh Quan",
      dropdown4: "Central Cold Storage (Block A)",
      readOnlySpecs: [
        { label: "Incubation Tank Temp", value: "42.0°C Stable", icon: "activity" },
        { label: "Live Bacteria Count", value: "≥ 10^7 CFU/g", icon: "flask" },
        { label: "Aloe Vera Pulp Ratio", value: "8.5% fiber clean", icon: "check-circle" },
        { label: "Traceability QR Code", value: "YOG-ALOE-091", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "04:00 AM", desc: "Inoculated Streptococcus thermophilus culture" },
        { time: "09:30 AM", desc: "Coagulation reached target pH 4.4" },
        { time: "10:15 AM", desc: "Blended thermal-sterilized aloe vera dice" }
      ],
      bannerType: "yogurt"
    },
    {
      id: "LOT-2026-092",
      category: "Nut & Grain Milk",
      title: "Walnut Oat Nut Milk 180ml Paper Pack",
      statValue: "8,000 / 8,000",
      statSub: "Cartons completed",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Nut Ratio", value: "14% California Walnuts" },
        { label: "Homogenization", value: "200 Bar 2-stage" },
        { label: "Line", value: "Line A2 - PET Bottle" },
        { label: "Shift Evaluation", value: "Waste loss < 0.4%" }
      ],
      avatars: [
        { initial: "LH", bg: "#2563EB", name: "Le Hai Dang" },
        { initial: "NT", bg: "#059669", name: "Nguyen Thu Ha" }
      ],
      status: "completed",
      statusLabel: "Ready for Storage",
      statusPill: "green",
      dropdown1: "completed",
      dropdown2: "Line A2 - PET Bottle 350ml",
      dropdown3: "Le Hai Dang",
      dropdown4: "Packaging Buffer Zone (Zone 2)",
      readOnlySpecs: [
        { label: "Grind Particle Fineness", value: "< 25 micron", icon: "activity" },
        { label: "Coliform Indicator", value: "Negative", icon: "shield" },
        { label: "Omega-3 Content", value: "120mg / 100ml", icon: "flask" },
        { label: "Traceability QR Code", value: "NUT-WALNUT-092", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "Yesterday 07:00", desc: "Soaked walnuts and enzymatic hydrolysis of oats" },
        { time: "Yesterday 16:00", desc: "Aseptic filling completed 8,000 cartons" },
        { time: "09:00 AM", desc: "Pallets shrink-wrapped awaiting warehouse transfer" }
      ],
      bannerType: "nuts"
    }
  ],

  qc: [
    {
      id: "QC-TEST-442",
      category: "Microbiological Testing",
      title: "Aloe Vera Yogurt Sample #LOT-2026-091",
      statValue: "18 / 20",
      statSub: "Criteria passed",
      progress: 90,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Sampler", value: "Eng. Do Duc Minh" },
        { label: "Inoculation Time", value: "08/09/2026 08:30" },
        { label: "Coliform Count", value: "< 10 CFU/ml (Negative)" },
        { label: "Preliminary Result", value: "Incubation colony count in progress" }
      ],
      avatars: [
        { initial: "DM", bg: "#0D9488", name: "Do Duc Minh" },
        { initial: "PT", bg: "#7C3AED", name: "Pham Thu Trang" }
      ],
      status: "pending",
      statusLabel: "Incubation in progress",
      statusPill: "amber",
      dropdown1: "pending",
      dropdown2: "Microbiology Lab #01",
      dropdown3: "MSc. Pham Thu Trang",
      dropdown4: "QCVN 5-1:2010/BYT",
      readOnlySpecs: [
        { label: "Petrifilm Plate", value: "3M Aerobic Count Plate", icon: "flask" },
        { label: "Incubation Period", value: "48 hours at 35°C ± 1°C", icon: "activity" },
        { label: "Salmonella", value: "Not detected in 25g", icon: "shield" },
        { label: "Lab Record ID", value: "LAB-MIC-2026-898", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "08:15 AM", desc: "Collected 5 random samples at filling nozzle #2" },
        { time: "09:00 AM", desc: "Prepared 10^-1 to 10^-3 serial dilutions" },
        { time: "11:00 AM", desc: "Placed in Memmert incubator at 37°C" }
      ],
      bannerType: "qc"
    },
    {
      id: "QC-TEST-443",
      category: "Physicochemical & Nutrition",
      title: "Orange Juice Pulp Sample #LOT-2026-090",
      statValue: "100%",
      statSub: "15/15 criteria passed",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Vitamin C Content", value: "48mg / 100ml" },
        { label: "Standard Brix", value: "12.8° (Allowable range 12.5-13.0)" },
        { label: "Preservatives", value: "None detected" },
        { label: "Conclusion", value: "Release Certificate Issued" }
      ],
      avatars: [
        { initial: "PT", bg: "#7C3AED", name: "Pham Thu Trang" }
      ],
      status: "passed",
      statusLabel: "Safety Standard Passed 100%",
      statusPill: "green",
      dropdown1: "passed",
      dropdown2: "Physicochemical Lab #02",
      dropdown3: "MSc. Pham Thu Trang",
      dropdown4: "ISO 22000:2018",
      readOnlySpecs: [
        { label: "Refractometer", value: "Atago Pocket PAL-1", icon: "activity" },
        { label: "Sensory Turbidity", value: "Homogeneous, natural", icon: "check-circle" },
        { label: "Heavy Metals Pb", value: "< 0.02 mg/kg (Standard)", icon: "shield" },
        { label: "Lab Test Code", value: "QC-CHEM-90-OK", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "Yesterday 16:30", desc: "Received sample from canning line" },
        { time: "Yesterday 19:00", desc: "HPLC organic acid profile tested" },
        { time: "This morning 08:30", desc: "Lab manager signed and stamped APPROVED" }
      ],
      bannerType: "juice"
    }
  ],

  "raw-materials": [
    {
      id: "RAW-LOT-512",
      category: "Oilseed",
      title: "Raw Shelled Peanuts (High Oleic Grade)",
      statValue: "2,000 / 2,000",
      statSub: "kg bulk bags",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Moisture Content", value: "6.8% (Spec < 8.0%)" },
        { label: "Aflatoxin B1", value: "Negative (< 2.0 ppb)" },
        { label: "Purity Grade", value: "Grade 1 (99.5%)" },
        { label: "Defect Rate", value: "0.2% (Visual Sorting)" }
      ],
      avatars: [
        { initial: "NT", bg: "#059669", name: "Nguyen Thu Ha" },
        { initial: "TM", bg: "#162B4E", name: "Tran Minh Quan" }
      ],
      status: "inspected",
      statusLabel: "Silo Intake Approved",
      statusPill: "green",
      dropdown1: "inspected",
      dropdown2: "Dry Aerated Silo A1",
      dropdown3: "Nguyen Thu Ha",
      dropdown4: "Golden Grain & Oilseed Co.",
      readOnlySpecs: [
        { label: "Truck Plate", value: "29C-772.33", icon: "truck" },
        { label: "Standard Unit", value: "kg", icon: "database" },
        { label: "Storage Temp", value: "Dry Aerated Silo 20°C", icon: "activity" },
        { label: "Supplier COA", value: "COA-PEANUT-2026-001", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "05:00 AM", desc: "Truck arrived at raw material gate" },
        { time: "05:30 AM", desc: "Aflatoxin rapid test passed (0.1 ppb)" },
        { time: "06:15 AM", desc: "Intake completed into Dry Aerated Silo A1" }
      ],
      bannerType: "milk"
    },
    {
      id: "RAW-LOT-513",
      category: "Grain",
      title: "Yellow Feed & Milling Corn Grade 1",
      statValue: "3,500 / 3,500",
      statSub: "kg aerated tote",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Moisture Content", value: "12.5% (Spec < 14.0%)" },
        { label: "Foreign Matter", value: "0.1%" },
        { label: "Broken Kernels", value: "1.2%" },
        { label: "Aflatoxin Spec", value: "Compliant (< 5 ppb)" }
      ],
      avatars: [
        { initial: "LH", bg: "#2563EB", name: "Le Hai Dang" }
      ],
      status: "inspected",
      statusLabel: "Intake Verified",
      statusPill: "green",
      dropdown1: "inspected",
      dropdown2: "Grain Silo B1",
      dropdown3: "Le Hai Dang",
      dropdown4: "Central Plains Farm Collective",
      readOnlySpecs: [
        { label: "Delivery Note", value: "BL-CORN-2026-088", icon: "database" },
        { label: "Bulk Density", value: "720 g/L", icon: "activity" },
        { label: "Warehouse Humidity", value: "Humidity 55% (Compliant)", icon: "check-circle" },
        { label: "Supplier Code", value: "SUP-003", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "07:30 AM", desc: "Delivery received at grain intake hopper" },
        { time: "08:15 AM", desc: "Foreign matter & density analysis complete" },
        { time: "09:00 AM", desc: "Stored in Grain Silo B1" }
      ],
      bannerType: "packages"
    },
    {
      id: "RAW-LOT-514",
      category: "Oilseed",
      title: "Black Sunflower Seeds (Oil Extraction Grade)",
      statValue: "1,800 / 1,800",
      statSub: "kg bulk tote",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Oil Content", value: "46.2% (High Yield)" },
        { label: "Moisture Content", value: "7.2% (Spec < 8.5%)" },
        { label: "Purity Grade", value: "99.2%" },
        { label: "Free Fatty Acids", value: "0.5% (Excellent)" }
      ],
      avatars: [
        { initial: "PT", bg: "#7C3AED", name: "Pham Thu Trang" }
      ],
      status: "inspected",
      statusLabel: "Cold Press Ready",
      statusPill: "green",
      dropdown1: "inspected",
      dropdown2: "Specialty Silo C3",
      dropdown3: "Nguyen Thu Ha",
      dropdown4: "Sunrise Agri Seeds Corp.",
      readOnlySpecs: [
        { label: "Seed Variety", value: "Black Confection / Oil hybrid", icon: "database" },
        { label: "Storage Condition", value: "Dry Cool Silo 18°C", icon: "activity" },
        { label: "Organic Standard", value: "USDA Organic / VietGAP", icon: "check-circle" },
        { label: "Supplier Code", value: "SUP-002", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "09:15 AM", desc: "Seeds unloaded into pre-cleaning aspirator" },
        { time: "10:30 AM", desc: "Moisture and oil content spectrometer test complete" },
        { time: "11:00 AM", desc: "Approved for production line feeding" }
      ],
      bannerType: "juice"
    }
  ],

  inventory: [
    {
      id: "INV-SKU-102",
      category: "Finished Oil Products",
      title: "Pure Roasted Peanut Oil 1L (Carton of 12)",
      statValue: "1,850",
      statSub: "Cartons in stock",
      progress: 85,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Pallet Location", value: "Cold Rack A3 - Tier 2" },
        { label: "Room Temperature", value: "4°C - 6°C" },
        { label: "Safety Stock Level", value: "Min 500 / Max 2,500" },
        { label: "Mfg Date", value: "02/09/2026" }
      ],
      avatars: [
        { initial: "HT", bg: "#0284C7", name: "Hoang Dinh Tuan" },
        { initial: "NT", bg: "#059669", name: "Nguyen Thu Ha" }
      ],
      status: "in_stock",
      statusLabel: "Ample Stock",
      statusPill: "green",
      dropdown1: "in_stock",
      dropdown2: "Aisle A - Rack 04 (Tier 3)",
      dropdown3: "Hoang Dinh Tuan",
      dropdown4: "FEFO (Nearest Expiry First)",
      readOnlySpecs: [
        { label: "Barcode EAN-13", value: "8935012345678", icon: "qr-code", mono: true },
        { label: "Pallet Weight", value: "780 kg / Pallet", icon: "database" },
        { label: "Remaining Shelf Life", value: "174 days (FEFO Rank A)", icon: "activity" },
        { label: "Packaging Spec", value: "12 packs x 1000ml", icon: "check-circle" }
      ],
      timeline: [
        { time: "02/09/2026", desc: "Received 2,000 cartons from processing plant" },
        { time: "05/09/2026", desc: "Dispatched 150 cartons to VinMart system" }
      ],
      bannerType: "milk"
    },
    {
      id: "INV-SKU-108",
      category: "Refreshment Beverages",
      title: "Bottled Honey Green Tea 450ml (Case of 24)",
      statValue: "210 / 1,000",
      statSub: "Replenishment needed",
      progress: 21,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Pallet Location", value: "Dry Rack D1 - Cell 09" },
        { label: "Minimum Threshold", value: "300 Cartons" },
        { label: "Status", value: "Below Safety Threshold" },
        { label: "Depletion Forecast", value: "2 days retail stock left" }
      ],
      avatars: [
        { initial: "HT", bg: "#0284C7", name: "Hoang Dinh Tuan" }
      ],
      status: "low_stock",
      statusLabel: "Low Stock Alert",
      statusPill: "amber",
      dropdown1: "low_stock",
      dropdown2: "Aisle C - FIFO Flow Rack",
      dropdown3: "Hoang Dinh Tuan",
      dropdown4: "FIFO (First In First Out)",
      readOnlySpecs: [
        { label: "Barcode EAN-13", value: "8935098765432", icon: "qr-code", mono: true },
        { label: "Current Pallet Count", value: "3.5 Pallets", icon: "database" },
        { label: "Pending Sales Order", value: "500 cartons (Mega Market)", icon: "activity" },
        { label: "Planning Proposal", value: "Prioritize Line A2 tomorrow", icon: "shield" }
      ],
      timeline: [
        { time: "07/09/2026", desc: "Dispatched 600 cartons to Circle K chain" },
        { time: "Today 08:30", desc: "Automated alert sent to Plant Manager" }
      ],
      bannerType: "juice"
    }
  ],

  dispatch: [
    {
      id: "DISP-2026-192",
      category: "Refrigerated Transport Order",
      title: "Distribution of 800 cartons UHT milk to Mega Market",
      statValue: "800 / 800",
      statSub: "Cartons loaded",
      progress: 100,
      progressColor: "fill-green",
      miniGrid: [
        { label: "Reefer Truck", value: "Stainless Truck 29C-8819" },
        { label: "Cargo Temperature", value: "3.8°C (Live GPS Telemetry)" },
        { label: "Departure Time", value: "10:30 AM (Today)" },
        { label: "Est. Arrival", value: "12:00 PM (Noon today)" }
      ],
      avatars: [
        { initial: "BH", bg: "#475569", name: "Driver Bui Van Hung" },
        { initial: "LH", bg: "#2563EB", name: "Le Hai Dang" }
      ],
      status: "dispatched",
      statusLabel: "In Transit on Highway",
      statusPill: "green",
      dropdown1: "dispatched",
      dropdown2: "Nam Ha Container Cold Logistics",
      dropdown3: "Driver Bui Van Hung",
      dropdown4: "Mega Market Central DC Binh Phu",
      readOnlySpecs: [
        { label: "Vehicle License Plate", value: "29C-881.99 (ThermoKing)", icon: "truck" },
        { label: "IoT Temperature Sensor", value: "4G Online - 3.8°C compliant", icon: "activity" },
        { label: "Waybill Number", value: "LOG-MM-2026-992", icon: "qr-code", mono: true },
        { label: "Handover Documentation", value: "Full Health Ministry quarantine certs", icon: "check-circle" }
      ],
      timeline: [
        { time: "09:30 AM", desc: "Loaded goods from cold rack A3 onto truck" },
        { time: "10:15 AM", desc: "Attached safety lead seal #9942" },
        { time: "10:30 AM", desc: "Truck departed through Gate 1" }
      ],
      bannerType: "truck"
    },
    {
      id: "DISP-2026-193",
      category: "Internal Transfer",
      title: "Transfer 350 cartons orange juice to transit hub",
      statValue: "120 / 350",
      statSub: "Loading pallets",
      progress: 34,
      progressColor: "fill-amber",
      miniGrid: [
        { label: "Receiving Vehicle", value: "5-ton Truck (Fleet Truck 04)" },
        { label: "Loading Dock", value: "Dock Gate #3 (Warehouse B)" },
        { label: "Priority", value: "Urgent - Customer requires by 14:00" },
        { label: "Tally Clerk", value: "Nguyen Van Thien" }
      ],
      avatars: [
        { initial: "NT", bg: "#059669", name: "Nguyen Van Thien" }
      ],
      status: "loading",
      statusLabel: "Loading at Dock",
      statusPill: "amber",
      dropdown1: "loading",
      dropdown2: "Factory Reefer Fleet (Truck 04)",
      dropdown3: "Nguyen Van Thien (Truck 29C-8819)",
      dropdown4: "VinMart Distribution Center Hanoi",
      readOnlySpecs: [
        { label: "Dispatch Dock", value: "Dock Gate #03", icon: "database" },
        { label: "Visual Inspection", value: "Intact seals, no dented boxes", icon: "shield" },
        { label: "Speed Limit", value: "Max 60 km/h (Liquid cargo)", icon: "activity" },
        { label: "Trip Code", value: "TRUCK-4T-0809", icon: "qr-code", mono: true }
      ],
      timeline: [
        { time: "10:30 AM", desc: "Truck docked, opening rear doors" },
        { time: "10:45 AM", desc: "Forklift loading first 4 pallets onto bed" }
      ],
      bannerType: "juice"
    }
  ]
};

// Application Database
let appData = JSON.parse(JSON.stringify(initialData));

// SVG Vector Banners for Detail Panel
function getBannerSvg(type, title, stat) {
  const backgrounds = {
    milk: 'linear-gradient(135deg, #1E293B 0%, #0F172A 50%, #1E3A8A 100%)',
    juice: 'linear-gradient(135deg, #78350F 0%, #451A03 50%, #B45309 100%)',
    yogurt: 'linear-gradient(135deg, #064E3B 0%, #022C22 50%, #047857 100%)',
    nuts: 'linear-gradient(135deg, #312E81 0%, #1E1B4B 50%, #4338CA 100%)',
    qc: 'linear-gradient(135deg, #134E4A 0%, #042F2E 50%, #0F766E 100%)',
    truck: 'linear-gradient(135deg, #18181B 0%, #09090B 50%, #27272A 100%)',
    packages: 'linear-gradient(135deg, #1E1B4B 0%, #0F172A 50%, #3730A3 100%)'
  };

  const bg = backgrounds[type] || backgrounds.milk;

  return `
    <div style="width:100%;height:100%;background:${bg};position:relative;display:flex;align-items:center;padding:0 24px;overflow:hidden;">
      <svg style="position:absolute;right:-20px;bottom:-20px;opacity:0.12;width:180px;height:180px;" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <div style="position:relative;z-index:2;">
        <div style="display:inline-block;padding:3px 8px;background:rgba(255,255,255,0.15);backdrop-filter:blur(4px);border-radius:4px;font-size:11px;font-weight:700;color:#FFFFFF;margin-bottom:6px;letter-spacing:0.5px;text-transform:uppercase;">
          FOOD MAN • HACCP APPROVED
        </div>
        <div style="color:#FFFFFF;font-size:18px;font-weight:800;letter-spacing:-0.3px;max-width:340px;line-height:1.3;">${title}</div>
        <div style="color:#93C5FD;font-size:12px;font-weight:600;margin-top:4px;font-family:'JetBrains Mono',monospace;">${stat}</div>
      </div>
    </div>
  `;
}

// Icon Helper for Technical Specs
function getIconSvg(name) {
  switch (name) {
    case 'flask':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 2v7.31L4.65 19.4c-.65.98.05 2.6 1.35 2.6h12c1.3 0 2-1.62 1.35-2.6L14 9.31V2m-4 0h4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    case 'activity':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    case 'check-circle':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" stroke-linecap="round" stroke-linejoin="round"/><polyline points="22 4 12 14.01 9 11.01" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    case 'qr-code':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>`;
    case 'database':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>`;
    case 'shield':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>`;
    case 'truck':
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>`;
    default:
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
  }
}

// Render Master Card List (2-Column Grid)
function renderCardList() {
  const cardContainer = document.getElementById('cardGridContainer');
  const items = appData[appState.currentDomain] || [];

  // Filter items
  const filteredItems = items.filter(item => {
    const matchesFilter = 
      appState.currentFilter === 'all' ||
      (appState.currentFilter === 'attention' && item.statusPill === 'amber') ||
      (appState.currentFilter === 'ready' && item.statusPill === 'green');

    const q = appState.searchQuery.toLowerCase().trim();
    const matchesSearch = !q || 
      item.id.toLowerCase().includes(q) ||
      item.title.toLowerCase().includes(q) ||
      item.category.toLowerCase().includes(q);

    return matchesFilter && matchesSearch;
  });

  // Update page counts
  const totalCountEl = document.getElementById('pageTotalCount');
  if (totalCountEl) {
    const config = domainConfigs[appState.currentDomain];
    totalCountEl.textContent = `${items.length} ${config.counterLabel}`;
  }

  // Update Filter Pill Counts
  const countAll = items.length;
  const countAttention = items.filter(i => i.statusPill === 'amber').length;
  const countReady = items.filter(i => i.statusPill === 'green').length;

  document.getElementById('filterCountAll').textContent = countAll;
  document.getElementById('filterCountAttention').textContent = countAttention;
  document.getElementById('filterCountReady').textContent = countReady;

  if (filteredItems.length === 0) {
    cardContainer.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: #FFFFFF; border-radius: 12px; border: 1px dashed var(--border-subtle);">
        <div style="width: 48px; height: 48px; margin: 0 auto 12px; border-radius: 50%; background: var(--accent-navy-light); display: flex; align-items: center; justify-content: center; color: var(--accent-navy);">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        </div>
        <h3 style="font-size: 16px; font-weight: 700; color: var(--text-main); margin-bottom: 4px;">No records found</h3>
        <p style="font-size: 13px; color: var(--text-muted);">Please try searching with another keyword or clear filter.</p>
      </div>
    `;
    return;
  }

  // Generate 2-Column Cards
  cardContainer.innerHTML = filteredItems.map(item => {
    const isSelected = item.id === appState.selectedCardId;

    // Build 2x2 mini-grid cells
    const miniGridHtml = item.miniGrid.map(cell => `
      <div class="mini-grid-cell">
        <span class="mini-grid-label">${cell.label}</span>
        <span class="mini-grid-value" title="${cell.value}">${cell.value}</span>
      </div>
    `).join('');

    // Build avatar stack
    const avatarsHtml = item.avatars.map(av => `
      <div class="avatar-stack-item" style="background-color: ${av.bg};" title="${av.name}">
        ${av.initial}
      </div>
    `).join('');

    // Build progress bar if available
    const progressHtml = item.progress !== undefined ? `
      <div class="card-progress-wrapper">
        <div class="card-progress-header">
          <span>Completion progress</span>
          <span style="font-family:'JetBrains Mono',monospace;">${item.progress}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-bar-fill ${item.progressColor || ''}" style="width: ${item.progress}%;"></div>
        </div>
      </div>
    ` : '';

    return `
      <div class="master-card ${isSelected ? 'active-selected' : ''}" data-id="${item.id}" onclick="handleCardSelect('${item.id}')">
        <!-- Header Row: ID/Title + secondary stat top-right -->
        <div class="card-header-row">
          <div class="card-title-group">
            <div class="card-id-tag">
              <span class="card-code">${item.id}</span>
              <span class="card-category-label">${item.category}</span>
            </div>
            <h3 class="card-item-title">${item.title}</h3>
          </div>
          <div class="card-stat-box">
            <span class="card-stat-value">${item.statValue}</span>
            <span class="card-stat-sub">${item.statSub}</span>
          </div>
        </div>

        <!-- 2x2 label/value mini-grid -->
        <div class="card-mini-grid">
          ${miniGridHtml}
        </div>

        <!-- Progress bar where relevant -->
        ${progressHtml}

        <!-- Card Footer: Avatar stack + Status pill bottom-right -->
        <div class="card-footer-row">
          <div class="avatar-stack">
            ${avatarsHtml}
          </div>
          <div class="status-pill pill-${item.statusPill}">
            <span class="status-dot"></span>
            <span>${item.statusLabel}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// Master-Detail Selection Handler
function handleCardSelect(cardId) {
  appState.selectedCardId = cardId;
  const items = appData[appState.currentDomain] || [];
  const item = items.find(i => i.id === cardId);

  if (!item) return;

  appState.activeItem = JSON.parse(JSON.stringify(item)); // Clone for editing

  // Re-render card grid to reflect active navy border
  renderCardList();

  // Populate and open slide-in panel
  populateDetailPanel(appState.activeItem);
  openDetailPanel();
}

// Open / Close Slide-in Panel
function openDetailPanel() {
  const panel = document.getElementById('detailSlidePanel');
  const backdrop = document.getElementById('slidePanelBackdrop');
  panel.classList.add('open');
  backdrop.classList.add('active');
}

function closeDetailPanel() {
  const panel = document.getElementById('detailSlidePanel');
  const backdrop = document.getElementById('slidePanelBackdrop');
  panel.classList.remove('open');
  backdrop.classList.remove('active');
  appState.selectedCardId = null;
  renderCardList();
}

// Populate Right-hand Slide-in Panel with Selected Card Data
function populateDetailPanel(item) {
  const config = domainConfigs[appState.currentDomain];

  // Set ID
  document.getElementById('panelRecordId').textContent = item.id;

  // Visual Banner at top
  const bannerContainer = document.getElementById('panelVisualBanner');
  bannerContainer.innerHTML = getBannerSvg(item.bannerType, item.title, `${item.statValue} ${item.statSub}`);

  // Editable Dropdown 1 (Status)
  const lbl1 = document.getElementById('labelDropdown1');
  lbl1.textContent = config.dropdown1Label;
  const sel1 = document.getElementById('selectDropdown1');
  sel1.innerHTML = config.dropdown1Options.map(opt => `
    <option value="${opt.value}" ${item.dropdown1 === opt.value ? 'selected' : ''}>${opt.label}</option>
  `).join('');

  // Editable Dropdown 2 (Line / Warehouse / Lab)
  const lbl2 = document.getElementById('labelDropdown2');
  lbl2.textContent = config.dropdown2Label;
  const sel2 = document.getElementById('selectDropdown2');
  sel2.innerHTML = config.dropdown2Options.map(opt => `
    <option value="${opt}" ${item.dropdown2 === opt ? 'selected' : ''}>${opt}</option>
  `).join('');

  // Editable Dropdown 3 (Lead / Inspector)
  const lbl3 = document.getElementById('labelDropdown3');
  lbl3.textContent = config.dropdown3Label;
  const sel3 = document.getElementById('selectDropdown3');
  sel3.innerHTML = config.dropdown3Options.map(opt => `
    <option value="${opt}" ${item.dropdown3 === opt ? 'selected' : ''}>${opt}</option>
  `).join('');

  // Editable Dropdown 4 (Storage / Standard)
  const lbl4 = document.getElementById('labelDropdown4');
  lbl4.textContent = config.dropdown4Label;
  const sel4 = document.getElementById('selectDropdown4');
  sel4.innerHTML = config.dropdown4Options.map(opt => `
    <option value="${opt}" ${item.dropdown4 === opt ? 'selected' : ''}>${opt}</option>
  `).join('');

  // Read-only technical info list below
  const specsContainer = document.getElementById('panelReadonlySpecs');
  if (item.readOnlySpecs && item.readOnlySpecs.length > 0) {
    specsContainer.innerHTML = item.readOnlySpecs.map(spec => `
      <div class="readonly-info-row">
        <span class="readonly-label">
          ${getIconSvg(spec.icon)}
          ${spec.label}
        </span>
        <span class="readonly-value ${spec.mono ? 'mono' : ''}">${spec.value}</span>
      </div>
    `).join('');
  } else {
    specsContainer.innerHTML = `<div style="padding: 12px 14px; font-size: 12px; color: var(--text-muted);">No technical specifications registered.</div>`;
  }

  // Timeline / Audit Log
  const timelineContainer = document.getElementById('panelTimelineList');
  if (item.timeline && item.timeline.length > 0) {
    timelineContainer.innerHTML = item.timeline.map(tl => `
      <div class="timeline-entry">
        <span class="timeline-time">${tl.time}</span>
        <span class="timeline-desc">${tl.desc}</span>
      </div>
    `).join('');
  } else {
    timelineContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted);">No activity log recorded.</div>`;
  }
}

// Save Changes from Slide-in Panel
function saveDetailPanelChanges() {
  if (!appState.activeItem) return;

  const config = domainConfigs[appState.currentDomain];
  const cardId = appState.activeItem.id;
  const items = appData[appState.currentDomain];
  const index = items.findIndex(i => i.id === cardId);

  if (index === -1) return;

  // Read updated dropdowns
  const val1 = document.getElementById('selectDropdown1').value;
  const val2 = document.getElementById('selectDropdown2').value;
  const val3 = document.getElementById('selectDropdown3').value;
  const val4 = document.getElementById('selectDropdown4').value;

  const opt1 = config.dropdown1Options.find(o => o.value === val1);
  if (opt1) {
    items[index].status = val1;
    items[index].statusLabel = opt1.label;
    items[index].statusPill = opt1.pill;
  }

  items[index].dropdown1 = val1;
  items[index].dropdown2 = val2;
  items[index].dropdown3 = val3;
  items[index].dropdown4 = val4;

  // Update relevant mini-grid value if matches
  if (items[index].miniGrid[1]) {
    items[index].miniGrid[1].value = val2;
  }

  // Add an entry to timeline
  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  items[index].timeline.unshift({
    time: `Today ${timeStr}`,
    desc: `Status updated: "${opt1 ? opt1.label : val1}" by Tran Minh Quan`
  });

  // Re-render
  renderCardList();
  populateDetailPanel(items[index]);
  showToast("Success!", `Successfully saved changes for record ${cardId}`, "success");
}

// Delete Record Action
function deleteCurrentRecord() {
  if (!appState.selectedCardId) return;
  const cardId = appState.selectedCardId;

  if (confirm(`Are you sure you want to delete record ${cardId} from the system?`)) {
    appData[appState.currentDomain] = appData[appState.currentDomain].filter(i => i.id !== cardId);
    closeDetailPanel();
    renderCardList();
    showToast("Record Deleted", `Record ${cardId} has been successfully deleted.`, "danger");
  }
}

// Switch Active Navigation Domain
function switchDomain(domainKey) {
  if (!domainConfigs[domainKey]) return;

  appState.currentDomain = domainKey;
  appState.selectedCardId = null;
  appState.searchQuery = '';
  appState.currentFilter = 'all';

  // Update Sidebar active classes
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.domain === domainKey);
  });

  // Update Filter buttons
  document.querySelectorAll('.filter-tab').forEach(el => {
    el.classList.toggle('active', el.dataset.filter === 'all');
  });

  // Update Breadcrumb & Header Title
  const config = domainConfigs[domainKey];
  const breadcrumbEl = document.getElementById('pageBreadcrumb');
  breadcrumbEl.innerHTML = config.breadcrumb.map((crumb, idx) => {
    if (idx === config.breadcrumb.length - 1) {
      return `<span class="breadcrumb-active">${crumb}</span>`;
    }
    return `<a href="javascript:void(0)">${crumb}</a><span class="breadcrumb-separator">/</span>`;
  }).join('');

  document.getElementById('pageMainTitle').textContent = config.title;
  document.getElementById('btnPrimaryActionText').textContent = config.createBtnText;

  // Clear search input
  const searchInput = document.getElementById('globalSearchInput');
  if (searchInput) searchInput.value = '';

  // Close detail panel if open
  closeDetailPanel();

  // Render cards for domain
  renderCardList();
}

// Open Quick Create Modal
function openQuickCreateModal(domainKey) {
  const targetDomain = domainKey || appState.currentDomain;
  const config = domainConfigs[targetDomain];

  document.getElementById('modalTargetDomain').value = targetDomain;
  document.getElementById('modalTitleText').textContent = `Create New: ${config.title}`;
  document.getElementById('newRecordCategory').value = config.dropdown2Options[0] || 'Chung';
  document.getElementById('newRecordTitle').value = '';
  document.getElementById('newRecordStat').value = `1,000 ${config.unit}`;

  const modal = document.getElementById('quickCreateModal');
  modal.classList.add('active');
}

function closeQuickCreateModal() {
  const modal = document.getElementById('quickCreateModal');
  modal.classList.remove('active');
}

function submitQuickCreate() {
  const targetDomain = document.getElementById('modalTargetDomain').value;
  const title = document.getElementById('newRecordTitle').value.trim();
  const category = document.getElementById('newRecordCategory').value.trim();
  const stat = document.getElementById('newRecordStat').value.trim();

  if (!title) {
    alert("Please enter a record name / title!");
    return;
  }

  const config = domainConfigs[targetDomain];
  const prefix = targetDomain === 'production' ? 'LOT' :
                 targetDomain === 'qc' ? 'QC' :
                 targetDomain === 'raw-materials' ? 'RAW' :
                 targetDomain === 'inventory' ? 'INV' : 'DISP';

  const randomNum = Math.floor(100 + Math.random() * 900);
  const newId = `${prefix}-2026-${randomNum}`;

  const newItem = {
    id: newId,
    category: category || "General Production",
    title: title,
    statValue: stat || `500 ${config.unit}`,
    statSub: "Newly created",
    progress: 10,
    progressColor: "fill-amber",
    miniGrid: [
      { label: "Creation Date", value: "Today 11:00" },
      { label: "Responsible Unit", value: config.dropdown2Options[0] },
      { label: "Approved By", value: "Tran Minh Quan" },
      { label: "Status", value: "Initializing" }
    ],
    avatars: [
      { initial: "TM", bg: "#162B4E", name: "Tran Minh Quan" }
    ],
    status: config.dropdown1Options[0].value,
    statusLabel: config.dropdown1Options[0].label,
    statusPill: config.dropdown1Options[0].pill,
    dropdown1: config.dropdown1Options[0].value,
    dropdown2: config.dropdown2Options[0],
    dropdown3: "Tran Minh Quan",
    dropdown4: config.dropdown4Options[0],
    readOnlySpecs: [
      { label: "System Init Code", value: newId, icon: "qr-code", mono: true },
      { label: "Compliance Standard", value: "QCVN 5-1:2010/BYT", icon: "shield" }
    ],
    timeline: [
      { time: "Just now", desc: "Initialized new record on Food Man system" }
    ],
    bannerType: targetDomain === 'qc' ? 'qc' : targetDomain === 'dispatch' ? 'truck' : 'milk'
  };

  appData[targetDomain].unshift(newItem);
  closeQuickCreateModal();

  if (appState.currentDomain === targetDomain) {
    renderCardList();
    handleCardSelect(newId);
  } else {
    switchDomain(targetDomain);
    handleCardSelect(newId);
  }

  showToast("Created Successfully!", `Added ${newId} to category ${config.title}`, "success");
}

// Toast System
function showToast(title, msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;

  const iconSvg = type === 'success' ? 
    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>` :
    type === 'danger' ?
    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>` :
    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;

  toast.innerHTML = `
    ${iconSvg}
    <div class="toast-content">
      <div class="toast-title">${title}</div>
      <div class="toast-msg">${msg}</div>
    </div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

// Live Topbar Clock (Date & Time chips)
function startLiveClock() {
  function updateTime() {
    const now = new Date();
    
    // Days in Vietnamese
    const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    const dayName = days[now.getDay()];
    const dateFormatted = `${String(now.getDate()).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')}/${now.getFullYear()}`;
    const timeFormatted = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    const dateChip = document.getElementById('liveDateChip');
    const timeChip = document.getElementById('liveTimeChip');

    if (dateChip) dateChip.textContent = `${dayName}, ${dateFormatted}`;
    if (timeChip) timeChip.textContent = timeFormatted;
  }

  updateTime();
  setInterval(updateTime, 1000);
}

// Attach Event Listeners on Page Load
document.addEventListener('DOMContentLoaded', () => {
  // Start live date/time chips
  startLiveClock();

  // Initial render
  switchDomain('production');

  // Search input listener
  const searchInput = document.getElementById('globalSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      appState.searchQuery = e.target.value;
      renderCardList();
    });
  }

  // Filter Tabs
  document.querySelectorAll('.filter-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      appState.currentFilter = tab.dataset.filter;
      renderCardList();
    });
  });

  // Global Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Esc closes panels
    if (e.key === 'Escape') {
      closeDetailPanel();
      closeQuickCreateModal();
    }
    // Ctrl+K / Cmd+K focuses search
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      searchInput.focus();
    }
  });
});
