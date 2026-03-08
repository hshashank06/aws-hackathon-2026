import { createContext, useContext, useState, ReactNode } from "react";
import { Hospital } from "../data/mockData";

interface SearchContextType {
  searchResults: Hospital[];
  searchId: string | null;
  agentChunks: string[];
  isStreaming: boolean;
  setSearchResults: (hospitals: Hospital[]) => void;
  setSearchId: (id: string | null) => void;
  setAgentChunks: React.Dispatch<React.SetStateAction<string[]>>;
  setIsStreaming: (streaming: boolean) => void;
  getHospitalById: (id: string) => Hospital | null;
}

const SearchContext = createContext<SearchContextType | undefined>(undefined);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [searchResults, setSearchResults] = useState<Hospital[]>([]);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [agentChunks, setAgentChunks] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);

  const getHospitalById = (id: string): Hospital | null => {
    return searchResults.find((h) => h.id === id) || null;
  };

  return (
    <SearchContext.Provider 
      value={{ 
        searchResults, 
        searchId, 
        agentChunks,
        isStreaming,
        setSearchResults, 
        setSearchId, 
        setAgentChunks,
        setIsStreaming,
        getHospitalById 
      }}
    >
      {children}
    </SearchContext.Provider>
  );
}

export function useSearch() {
  const context = useContext(SearchContext);
  if (context === undefined) {
    throw new Error("useSearch must be used within a SearchProvider");
  }
  return context;
}
