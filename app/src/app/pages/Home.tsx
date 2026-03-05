import { useState } from "react";
import { Search, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { ProgressiveSearchResults } from "../components/ProgressiveSearchResults";

export function Home() {
  const [searchQuery, setSearchQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!searchQuery.trim()) {
      return;
    }

    setHasSearched(true);
    setSubmittedQuery(searchQuery);
  };

  return (
    <div className="min-h-full bg-gradient-to-b from-blue-50 to-white">
      {/* Hero Section */}
      <div className={`transition-all duration-500 ${hasSearched ? "py-8" : "py-24"}`}>
        <div className="max-w-4xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <div className="inline-flex items-center gap-2 bg-white px-4 py-2 rounded-full shadow-sm mb-6">
              <Sparkles className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-medium text-gray-700">
                AI-Powered Healthcare Transparency
              </span>
            </div>
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              Find the Right Hospital for Your Needs
            </h1>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Get verified information about costs, insurance coverage, and patient experiences
              to make informed healthcare decisions.
            </p>
          </motion.div>

          {/* Search Bar */}
          <motion.form
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            onSubmit={handleSearch}
            className="relative"
          >
            <div className="relative">
              <Search className="absolute left-5 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Describe your healthcare needs (e.g., 'affordable cardiac surgery with good insurance coverage')"
                className="w-full pl-14 pr-4 py-5 rounded-2xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none text-base shadow-lg"
              />
            </div>
            <button
              type="submit"
              className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-blue-600 text-white px-8 py-3 rounded-xl hover:bg-blue-700 transition-colors font-medium"
            >
              Search
            </button>
          </motion.form>

          {/* Search Suggestions */}
          {!hasSearched && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="mt-4 flex flex-wrap gap-2 justify-center"
            >
              <span className="text-sm text-gray-500">Try:</span>
              {["cardiac surgery", "orthopedic care", "cancer treatment", "affordable surgery"].map(
                (suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setSearchQuery(suggestion)}
                    className="text-sm bg-white px-3 py-1 rounded-full border border-gray-200 hover:border-blue-500 hover:text-blue-600 transition-colors"
                  >
                    {suggestion}
                  </button>
                )
              )}
            </motion.div>
          )}
        </div>
      </div>

      {/* Search Results */}
      <AnimatePresence>
        {hasSearched && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="max-w-7xl mx-auto px-6 pb-12"
          >
            <ProgressiveSearchResults query={submittedQuery} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}