"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge, Button, Card, Flex, Skeleton, Stack, Text } from "@chakra-ui/react"

type UserAuditEvent = {
  id: number
  actor: string
  subject: string
  action: string
  created_at: string
  message: string
  reason: string
  changed_fields: string[]
}

type AuditLogResponse = {
  events: UserAuditEvent[]
  total: number
  detail?: string
}

function formatTimestamp(value: string) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

export default function UserLogsList() {
  const [events, setEvents] = useState<UserAuditEvent[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch("/api/auth/user-audit-log", {
        method: "GET",
        cache: "no-store",
      })
      const payload = (await response.json()) as AuditLogResponse
      if (!response.ok) {
        throw new Error(payload.detail || "Unable to load user logs.")
      }
      setEvents(payload.events)
      setTotal(payload.total)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load user logs.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadEvents()
  }, [loadEvents])

  return (
    <Card.Root w="full" variant="outline">
      <Card.Header>
        <Flex justify="space-between" align="flex-start" gap={3}>
          <Stack gap={1}>
            <Card.Title>User Logs</Card.Title>
            <Card.Description>
              Audit events from the last year. Showing up to the latest 100 of {total}.
            </Card.Description>
          </Stack>
          <Button size="sm" variant="outline" onClick={() => void loadEvents()} loading={loading}>
            Refresh
          </Button>
        </Flex>
      </Card.Header>
      <Card.Body>
        {loading ? (
          <Stack gap={3}>
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} h="16" rounded="md" />
            ))}
          </Stack>
        ) : error ? (
          <Text color="red.500">{error}</Text>
        ) : events.length === 0 ? (
          <Text color="gray.500">No audit events have been recorded in the last year.</Text>
        ) : (
          <Stack gap={4}>
            {events.map((event) => (
              <Flex
                key={event.id}
                direction={{ base: "column", md: "row" }}
                justify="space-between"
                gap={2}
                borderBottomWidth="1px"
                pb={3}
                _last={{ borderBottomWidth: 0, pb: 0 }}
              >
                <Stack gap={1}>
                  <Flex gap={2} align="center" wrap="wrap">
                    <Badge colorPalette="blue" variant="subtle">{event.action}</Badge>
                    <Text fontWeight="medium">{event.actor}</Text>
                  </Flex>
                  <Text fontSize="sm" color="gray.600">
                    {event.subject}
                  </Text>
                  {event.message && <Text fontSize="sm">{event.message}</Text>}
                  {event.reason && <Text fontSize="sm" color="gray.600">Reason: {event.reason}</Text>}
                  {event.changed_fields.length > 0 && (
                    <Text fontSize="sm" color="gray.600">
                      Changed fields: {event.changed_fields.join(", ")}
                    </Text>
                  )}
                </Stack>
                <Text fontSize="sm" color="gray.500" whiteSpace="nowrap">
                  {formatTimestamp(event.created_at)}
                </Text>
              </Flex>
            ))}
          </Stack>
        )}
      </Card.Body>
    </Card.Root>
  )
}
