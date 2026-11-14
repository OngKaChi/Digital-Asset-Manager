import ForgotPasswordView from "@/components/auth/ForgotPassword"
import ThemeToggle from "@/components/ui/ThemeToggle"
import { Flex, Heading, Stack, Text } from "@chakra-ui/react"

export default function ForgotPasswordPage() {
  return (
    <Flex
      minH="100vh"
      w="full"
      align="center"
      justify="center"
      px={{ base: 4, md: 6 }}
      py={{ base: 12, md: 16 }}
      gap={6}
    >
      <ThemeToggle />
      <Stack gap={6} align="center">
        <Stack gap={2} textAlign="center">
          <Heading size="lg">Forgot password</Heading>
          <Text color="gray.500">Enter your email to request a password reset.</Text>
        </Stack>
        <ForgotPasswordView />
      </Stack>
    </Flex>
  )
}
