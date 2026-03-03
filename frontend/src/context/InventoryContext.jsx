import { createContext, useContext, useState } from 'react';

const CATEGORIES = ['Snacks', 'Staples', 'Edible Oil'];
const DEFAULT_INVENTORY = { Snacks: 2800, Staples: 5100, 'Edible Oil': 1900 };
const DEFAULT_LEAD_TIMES = { Snacks: 5, Staples: 7, 'Edible Oil': 10 };

const InventoryContext = createContext(null);

export const InventoryProvider = ({ children }) => {
  const [inventory, setInventory] = useState(DEFAULT_INVENTORY);
  const [leadTimes] = useState(DEFAULT_LEAD_TIMES);

  return (
    <InventoryContext.Provider value={{ categories: CATEGORIES, inventory, setInventory, leadTimes }}>
      {children}
    </InventoryContext.Provider>
  );
};

export const useInventory = () => {
  const ctx = useContext(InventoryContext);
  if (!ctx) throw new Error('useInventory must be used within InventoryProvider');
  return ctx;
};
