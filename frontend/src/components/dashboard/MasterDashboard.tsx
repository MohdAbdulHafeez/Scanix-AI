"use client";

import { motion } from "framer-motion";
import { ScanReport } from "../../types/scanix";
import ProductPassport from "./ProductPassport";
import NutritionGrid from "./NutritionGrid";
import IntelligenceRadar from "./IntelligenceRadar";
import EvidencePanel from "./EvidencePanel";

export default function MasterDashboard({ report }: { report: ScanReport }) {
  const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.1 } } };
  const item = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } };

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="w-full">
      <div className="grid grid-cols-12 gap-6 auto-rows-fr">
        <motion.div variants={item} className="col-span-12 xl:col-span-8">
          <ProductPassport report={report} />
        </motion.div>
        
        <motion.div variants={item} className="col-span-12 xl:col-span-4">
          <EvidencePanel report={report} />
        </motion.div>

        <motion.div variants={item} className="col-span-12 lg:col-span-7">
          <NutritionGrid report={report} />
        </motion.div>

        <motion.div variants={item} className="col-span-12 lg:col-span-5">
          <IntelligenceRadar report={report} />
        </motion.div>
      </div>
    </motion.div>
  );
}