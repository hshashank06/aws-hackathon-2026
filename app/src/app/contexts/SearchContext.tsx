import { createContext, useContext, useState, ReactNode } from "react";
import { Hospital } from "../data/mockData";

interface SearchContextType {
  searchResults: Hospital[];
  searchId: string | null;
  setSearchResults: (hospitals: Hospital[]) => void;
  setSearchId: (id: string | null) => void;
  getHospitalById: (id: string) => Hospital | null;
}

const SearchContext = createContext<SearchContextType | undefined>(undefined);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [searchResults, setSearchResults] = useState<Hospital[]>([]);
  const [searchId, setSearchId] = useState<string | null>(null);

  const getHospitalById = (id: string): Hospital | null => {
    return searchResults.find((h) => h.id === id) || null;
  };

  return (
    <SearchContext.Provider value={{ searchResults, searchId, setSearchResults, setSearchId, getHospitalById }}>
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
