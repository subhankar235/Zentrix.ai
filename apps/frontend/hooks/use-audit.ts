'use client';

import { useQuery } from '@tanstack/react-query';
import { auditApi } from '../lib/api/audit';

export function useAuditQuery(limit = 20) {
  return useQuery({
    queryKey: ['audit', { limit }],
    queryFn: () => auditApi.list(limit),
  });
}
