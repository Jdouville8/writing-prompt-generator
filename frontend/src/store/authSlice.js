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
      // Save token to localStorage
      if (action.payload.token) {
        localStorage.setItem('token', action.payload.token);
      }
    },
    logoutUser: (state) => {
      state.user = null;
      state.isAuthenticated = false;
      // Remove token from localStorage
      localStorage.removeItem('token');
    },
    setLoading: (state, action) => {
      state.loading = action.payload;
    },
  },
});

export const { loginUser, logoutUser, setLoading } = authSlice.actions;
export default authSlice.reducer;