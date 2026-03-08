/**
 * Agent Activity Stream Component
 * Displays real-time AI agent activity during hospital search
 */

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles } from 'lucide-react';

interface AgentActivityStreamProps {
  chunks: string[];
  isActive: boolean;
}

export function AgentActivityStream({ chunks, isActive }: AgentActivityStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new chunks arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [chunks]);

  if (!isActive && chunks.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="mb-6"
    >
      <div className="bg-white/60 backdrop-blur-sm border border-blue-200 rounded-xl p-4 shadow-sm">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3">
          <div className="relative">
            <Sparkles className="w-5 h-5 text-blue-600" />
            {isActive && (
              <motion.div
                className="absolute inset-0 bg-blue-400 rounded-full"
                animate={{
                  scale: [1, 1.5, 1],
                  opacity: [0.5, 0, 0.5],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
              />
            )}
          </div>
          <h3 className="text-sm font-semibold text-gray-900">
            {isActive ? 'AI Agent Working...' : 'Search Complete'}
          </h3>
        </div>

        {/* Activity Log */}
        <div
          ref={containerRef}
          className="max-h-48 overflow-y-auto space-y-2 text-sm text-gray-700 font-mono"
          style={{
            scrollbarWidth: 'thin',
            scrollbarColor: '#cbd5e1 #f1f5f9',
          }}
        >
          <AnimatePresence mode="popLayout">
            {chunks.map((chunk, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3 }}
                className="whitespace-pre-wrap leading-relaxed"
              >
                {chunk}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing indicator when active */}
          {isActive && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-1 text-blue-600"
            >
              <motion.span
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                ●
              </motion.span>
              <motion.span
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
              >
                ●
              </motion.span>
              <motion.span
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.5, repeat: Infinity, delay: 0.4 }}
              >
                ●
              </motion.span>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
