import { createContext, useContext } from 'react';

export const InventoryContext = createContext(null);

export const useInventory = () => {
  const ctx = useContext(InventoryContext);
  if (!ctx) throw new Error('useInventory must be used within InventoryProvider');
  return ctx;
};

