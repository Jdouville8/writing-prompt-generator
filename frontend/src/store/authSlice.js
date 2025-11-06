import { createSlice } from '@reduxjs/toolkit';

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    isAuthenticated: false,
    loading: false,
  },
  reducers: {
    loginUser: (state, action) => {
      state.user = action.payload.user;
      state.isAuthenticated = true;
      state.loading = false;
      // Save token and user to localStorage
      if (action.payload.token) {
        localStorage.setItem('token', action.payload.token);
        localStorage.setItem('user', JSON.stringify(action.payload.user));
      }
    },
    logoutUser: (state) => {
      state.user = null;
      state.isAuthenticated = false;
      // Remove token and user from localStorage
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    },
    restoreUser: (state, action) => {
      state.user = action.payload.user;
      state.isAuthenticated = true;
      state.loading = false;
    },
    setLoading: (state, action) => {
      state.loading = action.payload;
    },
  },
});

export const { loginUser, logoutUser, restoreUser, setLoading } = authSlice.actions;
export default authSlice.reducer;
