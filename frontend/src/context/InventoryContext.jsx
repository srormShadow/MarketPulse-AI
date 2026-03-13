import { useEffect, useState } from 'react';
import { InventoryContext } from './inventoryStore';
import { apiClient } from '../api/client';
import { useAuth } from './AuthContext';

const EMPTY_STATE = {
  categories: [],
  inventory: {},
  leadTimes: {},
  onboarding: { isEmpty: true, steps: [] },
};

export const InventoryProvider = ({ children }) => {
  const { user } = useAuth();
  const [categories, setCategories] = useState(EMPTY_STATE.categories);
  const [inventory, setInventory] = useState(EMPTY_STATE.inventory);
  const [leadTimes, setLeadTimes] = useState(EMPTY_STATE.leadTimes);
  const [loading, setLoading] = useState(true);
  const [onboarding, setOnboarding] = useState(EMPTY_STATE.onboarding);

  const refresh = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/dashboard/bootstrap');
      const data = res?.data || {};
      setCategories(Array.isArray(data.categories) ? data.categories : []);
      setInventory(data.inventory || {});
      setLeadTimes(data.lead_times || {});
      setOnboarding({
        isEmpty: Boolean(data.is_empty),
        steps: Array.isArray(data.onboarding_steps) ? data.onboarding_steps : [],
        hasCatalog: Boolean(data.has_catalog),
        hasSales: Boolean(data.has_sales),
        hasShopify: Boolean(data.has_shopify),
      });
    } catch {
      setCategories([]);
      setInventory({});
      setLeadTimes({});
      setOnboarding({ isEmpty: true, steps: [] });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      refresh();
      return;
    }
    setCategories([]);
    setInventory({});
    setLeadTimes({});
    setOnboarding({ isEmpty: true, steps: [] });
    setLoading(false);
  }, [user]);

  return (
    <InventoryContext.Provider value={{ categories, inventory, setInventory, leadTimes, setLeadTimes, loading, onboarding, refresh }}>
      {children}
    </InventoryContext.Provider>
  );
};

