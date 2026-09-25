import '../../i18n';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { ApiError, api } from '../../api/client';
import { LoginScreen } from '../LoginScreen';

jest.mock('../../api/client', () => ({ ...jest.requireActual('../../api/client'), api: { login: jest.fn(), signup: jest.fn() } }));
jest.mock('expo-secure-store', () => ({ getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn() }));
jest.mock('expo-sqlite', () => ({ openDatabaseAsync: jest.fn() }));
const mockedApi = jest.mocked(api);

describe('LoginScreen', () => {
  beforeEach(() => { jest.clearAllMocks(); });

  test('signs in by default', async () => {
    const onAuthenticated = jest.fn(); mockedApi.login.mockResolvedValue();
    const screen = await render(<LoginScreen onAuthenticated={onAuthenticated} />);
    await fireEvent.changeText(screen.getByLabelText('Email'), 'agent@example.com');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'long-enough-1');
    await fireEvent.press(screen.getByText('Sign in'));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalled());
    expect(mockedApi.login).toHaveBeenCalledWith('agent@example.com', 'long-enough-1');
    expect(mockedApi.signup).not.toHaveBeenCalled();
  });

  test('creates an account from the sign-up mode', async () => {
    const onAuthenticated = jest.fn(); mockedApi.signup.mockResolvedValue();
    const screen = await render(<LoginScreen onAuthenticated={onAuthenticated} />);
    await fireEvent.press(screen.getByText('New to Homean? Create an account'));
    await fireEvent.changeText(screen.getByLabelText('Email'), 'new@example.com');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'long-enough-1');
    await fireEvent.press(screen.getByText('Create account'));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalled());
    expect(mockedApi.signup).toHaveBeenCalledWith('new@example.com', 'long-enough-1');
    expect(mockedApi.login).not.toHaveBeenCalled();
  });

  test('explains an email that is already registered', async () => {
    mockedApi.signup.mockRejectedValue(new ApiError(409, 'conflict'));
    const screen = await render(<LoginScreen onAuthenticated={jest.fn()} />);
    await fireEvent.press(screen.getByText('New to Homean? Create an account'));
    await fireEvent.changeText(screen.getByLabelText('Email'), 'taken@example.com');
    await fireEvent.changeText(screen.getByLabelText('Password'), 'long-enough-1');
    await fireEvent.press(screen.getByText('Create account'));
    expect(await screen.findByText('An account with this email already exists. Sign in instead.')).toBeTruthy();
  });
});
