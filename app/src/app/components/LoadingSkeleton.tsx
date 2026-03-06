import { motion } from "motion/react";

export function HospitalCardSkeleton() {
  return (
    <div className="bg-white rounded-lg border-2 border-gray-200 shadow-sm p-6 animate-pulse">
      {/* Header Section */}
      <div className="flex gap-4 mb-4">
        <div className="w-16 h-16 rounded-lg bg-gray-200"></div>
        <div className="flex-1">
          <div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
        </div>
      </div>

      {/* Description */}
      <div className="space-y-2 mb-4">
        <div className="h-4 bg-gray-200 rounded w-full"></div>
        <div className="h-4 bg-gray-200 rounded w-5/6"></div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-gray-100 rounded-lg p-3 h-20"></div>
        <div className="bg-gray-100 rounded-lg p-3 h-20"></div>
        <div className="bg-gray-100 rounded-lg p-3 h-20"></div>
      </div>

      {/* Tags */}
      <div className="flex gap-2 mb-4">
        <div className="h-6 bg-gray-200 rounded-full w-20"></div>
        <div className="h-6 bg-gray-200 rounded-full w-24"></div>
        <div className="h-6 bg-gray-200 rounded-full w-16"></div>
      </div>

      {/* AI Recommendation */}
      <div className="bg-gray-100 rounded-lg p-4 h-32"></div>
    </div>
  );
}

export function LoadingSpinner({ className }: { className?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <motion.div
        className={className || "w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full"}
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
      />
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-4 text-gray-600 font-medium"
      >
        Searching hospitals...
      </motion.p>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="text-sm text-gray-500"
      >
        Analyzing verified reviews and costs
      </motion.p>
    </div>
  );
}
